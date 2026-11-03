"""Review pipeline shared by the Discord bot and the CLI (no Discord imports)."""
import json
from pathlib import Path

from . import draft, llm, metrics, prompts, trend, validate
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


PATCH_NOTES = Path(__file__).resolve().parent.parent / "data" / "patch_notes.md"


async def build_draft(od, account_id, enemies, pool=None, top=3):
    """Rank pool heroes (default: the player's most played) against known enemy heroes."""
    labels = await od.hero_labels()
    ids = {}
    for name in enemies + (pool or []):
        hid = await od.hero_id_by_name(name)
        if hid is None:
            raise OpenDotaError(f"Unknown hero '{name}'.")
        ids[name] = hid
    enemy_ids = [ids[n] for n in enemies]
    personal = await od.player_heroes(account_id, lobby_type=7, lane_role=2)  # mid only
    if pool:
        cands = [ids[n] for n in pool]
    else:
        cands = [h for h in sorted(personal, key=lambda h: -personal[h][0]) if personal[h][0] >= 3][:8]  # 1-2 game heroes are noise
    cands = [h for h in cands if h not in enemy_ids]
    if not cands:
        raise OpenDotaError("No candidate heroes. Pass a pool.")
    stats, tier = await od.hero_stats(), await od.rank_tier(account_id)
    matchups = {h: await od.matchups(h) for h in cands}
    ranked = draft.rank_candidates(cands, stats, matchups, personal, enemy_ids, tier)[:top]
    for r in ranked:
        r["hero"] = labels[r["hero"]]
        for m in r["matchups"]:
            m["enemy"] = labels[m["enemy"]]
    payload = {"rank_tier": tier, "enemies": [labels[h] for h in enemy_ids], "candidates": ranked}
    if PATCH_NOTES.exists():
        names = [r["hero"] for r in ranked] + payload["enemies"]
        payload["patch_notes"] = draft.hero_sections(PATCH_NOTES.read_text(), names)
    return await _ask_validated(prompts.DRAFT_SYSTEM, payload)
