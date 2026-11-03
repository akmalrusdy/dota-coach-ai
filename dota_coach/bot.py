import logging
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from .db import DB
from .opendota import OpenDota, OpenDotaError
from .review import advise, build_draft, build_trend, fetch_metrics, resolve_player, to_account_id

LIMIT = 1990

load_dotenv()
log = logging.getLogger("dota_coach")
bot = discord.Client(intents=discord.Intents.default())
tree = app_commands.CommandTree(bot)
db = DB()
od = OpenDota(os.getenv("OPENDOTA_API_KEY"))


def chunks(text, limit=LIMIT):
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        while len(line) > limit:  # single huge line: hard split
            out.append(line[:limit])
            line = line[limit:]
        if len(cur) + len(line) > limit:
            out.append(cur)
            cur = ""
        cur += line
    if cur.strip():
        out.append(cur)
    return out


async def build_review(discord_id, match_id, player_arg=None):
    if player_arg:
        account_id, hero_id = await resolve_player(od, player_arg)
    else:
        account_id, hero_id = db.account_id(discord_id), None
        if account_id is None:
            raise OpenDotaError("Link your account first with `/link <steam_id>`, or pass a player/hero.")
    m, player_account = await fetch_metrics(od, match_id, account_id, hero_id)
    advice = await advise(m)
    db.save_review(discord_id, player_account, match_id, m, advice)
    return f"**Match {match_id} - {m['hero']}** ({'W' if m['won'] else 'L'})\n{advice}"


async def respond(interaction, coro):
    await interaction.response.defer(thinking=True)
    try:
        text = await coro
    except OpenDotaError as e:
        text = str(e)
    except Exception:
        log.exception("review failed")
        text = "Something broke. Check the bot logs."
    parts = chunks(text)
    await interaction.followup.send(parts[0])
    for p in parts[1:]:
        await interaction.followup.send(p)


@tree.command(description="Link your Steam ID (needed for /lastmatch and default /review)")
async def link(interaction: discord.Interaction, steam_id: str):
    if not steam_id.isdigit():
        return await interaction.response.send_message("Steam ID must be digits.", ephemeral=True)
    db.link(interaction.user.id, to_account_id(int(steam_id)))
    await interaction.response.send_message(
        "Linked. In Dota 2 settings > Options > Social, enable **Expose Public Match Data**, "
        "otherwise OpenDota can't see your matches.",
        ephemeral=True,
    )


@tree.command(description="Review a match. Optional player: account id or hero name")
async def review(interaction: discord.Interaction, match_id: int, player: str | None = None):
    await respond(interaction, build_review(interaction.user.id, match_id, player))


async def _last(discord_id):
    account_id = db.account_id(discord_id)
    if account_id is None:
        raise OpenDotaError("Link your account first with `/link <steam_id>`.")
    return await build_review(discord_id, await od.recent_match_id(account_id))


@tree.command(description="Review your most recent match")
async def lastmatch(interaction: discord.Interaction):
    await respond(interaction, _last(interaction.user.id))


@tree.command(description="Trend over your recent ranked mid matches (takes a minute or two)")
@app_commands.describe(matches="How many matches, 5-20 (default 10)")
async def trend(interaction: discord.Interaction, matches: app_commands.Range[int, 5, 20] = 10):
    async def run():
        account_id = db.account_id(interaction.user.id)
        if account_id is None:
            raise OpenDotaError("Link your account first with `/link <steam_id>`.")
        return await build_trend(od, account_id, matches)

    await respond(interaction, run())


@tree.command(description="Pick suggestions vs the enemy heroes you can already see")
@app_commands.describe(enemy="Enemy heroes, comma separated", pool="Your candidate heroes, comma separated (default: your most played)")
async def draft(interaction: discord.Interaction, enemy: str, pool: str = ""):
    async def run():
        account_id = db.account_id(interaction.user.id)
        if account_id is None:
            raise OpenDotaError("Link your account first with `/link <steam_id>`.")
        split = lambda t: [x.strip() for x in t.split(",") if x.strip()]
        return await build_draft(od, account_id, split(enemy), split(pool) or None)

    await respond(interaction, run())


@bot.event
async def on_ready():
    await tree.sync()
    log.info("ready as %s", bot.user)


def main():
    logging.basicConfig(level=logging.INFO)
    bot.run(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    main()
