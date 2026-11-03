"""Review pipeline shared by the Discord bot and the CLI (no Discord imports)."""
import json

from . import llm, metrics, prompts, trend, validate
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
    return await _ask_validated(prompts.REVIEW_SYSTEM, m)


async def _ask_validated(system, payload):
    reply = await llm.ask([
        {"role": "system", "content": system},
        {"role": "user", "content": "Metrics:\n" + json.dumps(payload)},
    ])
    text = reply.content or "No advice generated."
    bad = validate.unverified_numbers(text, payload)
    if bad:
        text += f"\n-# Unverified numbers (not in the metrics): {', '.join(bad)}"
    return text


async def build_trend(od, account_id, want=10, lobby_type=7, scan=40):
    """Trend over the last `want` parsed ranked mid matches. Unparsed ones get a parse request."""
    rows = await od.recent_matches(account_id, scan, lobby_type=lobby_type)
    names, items = await od.hero_names(), await od.items()
    ms, unparsed, not_mid = [], 0, 0
    for r in rows:
        if len(ms) >= want:
            break
        match = await od.match(r["match_id"])
        if not metrics.is_parsed(match):
            unparsed += 1
            await od.request_parse(r["match_id"])
            continue
        p = metrics.find_player(match, account_id)
        if p is None or p.get("lane_role") != 2 or p.get("is_roaming"):
            not_mid += 1
            continue
        ms.append(metrics.compute_metrics(match, p, names, items))
    head = f"**Trend: {len(ms)} ranked mid matches** ({unparsed} unparsed, parse requested; {not_mid} non-mid skipped)"
    if not ms:
        raise OpenDotaError(head + "\nNo parsed ranked mid matches yet. Retry in a few minutes.")
    agg = trend.summarize(ms)
    return head + "\n" + await _ask_validated(prompts.TREND_SYSTEM, agg)
