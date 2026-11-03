import json
import logging
import os

import discord
from discord import app_commands
from dotenv import load_dotenv

from . import llm, metrics, prompts
from .db import DB
from .opendota import OpenDota, OpenDotaError

STEAM64_BASE = 76561197960265728
LIMIT = 1990

load_dotenv()
log = logging.getLogger("dota_coach")
bot = discord.Client(intents=discord.Intents.default())
tree = app_commands.CommandTree(bot)
db = DB()
od = OpenDota(os.getenv("OPENDOTA_API_KEY"))


def to_account_id(steam_id: int) -> int:
    return steam_id - STEAM64_BASE if steam_id > STEAM64_BASE else steam_id


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
    account_id = hero_id = None
    if player_arg:
        if player_arg.isdigit():
            account_id = to_account_id(int(player_arg))
        else:
            hero_id = await od.hero_id_by_name(player_arg)
            if hero_id is None:
                raise OpenDotaError(f"Unknown hero '{player_arg}'.")
    else:
        account_id = db.account_id(discord_id)
        if account_id is None:
            raise OpenDotaError("Link your account first with `/link <steam_id>`, or pass a player/hero.")

    match = await od.match(match_id)
    if not metrics.is_parsed(match):
        await od.request_parse(match_id)
        raise OpenDotaError("Match not parsed yet. Parse requested, retry in a few minutes.")
    player = metrics.find_player(match, account_id, hero_id)
    if player is None:
        raise OpenDotaError("Player not found in that match (private profile, or wrong id/hero).")

    m = metrics.compute_metrics(match, player, await od.hero_names(), await od.item_costs())
    reply = await llm.ask([
        {"role": "system", "content": prompts.REVIEW_SYSTEM},
        {"role": "user", "content": "Metrics:\n" + json.dumps(m)},
    ])
    advice = reply.content or "No advice generated."
    db.save_review(discord_id, player.get("account_id"), match_id, m, advice)
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


@bot.event
async def on_ready():
    await tree.sync()
    log.info("ready as %s", bot.user)


def main():
    logging.basicConfig(level=logging.INFO)
    bot.run(os.environ["DISCORD_TOKEN"])


if __name__ == "__main__":
    main()
