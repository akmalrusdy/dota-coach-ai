"""Review pipeline shared by the Discord bot and the CLI (no Discord imports)."""
import json

from . import llm, metrics, prompts, validate
from .opendota import OpenDotaError

STEAM64_BASE = 76561197960265728


def to_account_id(steam_id: int) -> int:
    return steam_id - STEAM64_BASE if steam_id > STEAM64_BASE else steam_id


async def resolve_player(od, player_arg):
    """'12345' or steam64 -> (account_id, None); hero name -> (None, hero_id)."""
    if player_arg.isdigit():
        return to_account_id(int(player_arg)), None
    hero_id = await od.hero_id_by_name(player_arg)
    if hero_id is None:
        raise OpenDotaError(f"Unknown hero '{player_arg}'.")
    return None, hero_id


async def fetch_metrics(od, match_id, account_id=None, hero_id=None):
    match = await od.match(match_id)
    if not metrics.is_parsed(match):
        await od.request_parse(match_id)
        raise OpenDotaError("Match not parsed yet. Parse requested, retry in a few minutes.")
    player = metrics.find_player(match, account_id, hero_id)
    if player is None:
        raise OpenDotaError("Player not found in that match (private profile, or wrong id/hero).")
    m = metrics.compute_metrics(match, player, await od.hero_names(), await od.items())
    return m, player.get("account_id")


async def advise(m):
    reply = await llm.ask([
        {"role": "system", "content": prompts.REVIEW_SYSTEM},
        {"role": "user", "content": "Metrics:\n" + json.dumps(m)},
    ])
    advice = reply.content or "No advice generated."
    bad = validate.unverified_numbers(advice, m)
    if bad:
        advice += f"\n-# Unverified numbers (not in the metrics): {', '.join(bad)}"
    return advice
