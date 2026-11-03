"""Aggregate many matches' metrics into trend numbers. Pure functions."""
from statistics import median


def _med(xs):
    xs = [x for x in xs if x is not None]
    return round(median(xs), 1) if xs else None


def summarize(ms):
    lane = lambda m: m.get("lane") or {}
    wins = [m for m in ms if m["won"]]
    losses = [m for m in ms if not m["won"]]
    heroes = {}
    for m in ms:
        h = heroes.setdefault(m["hero"].removeprefix("npc_dota_hero_"), {"games": 0, "wins": 0})
        h["games"] += 1
        h["wins"] += m["won"]
    lh_diff = [
        m["at_10"]["lh"] - lane(m)["opponent_lh_at_10"]
        for m in ms
        if m["at_10"]["lh"] is not None and lane(m).get("opponent_lh_at_10") is not None
    ]
    return {
        "matches": len(ms),
        "wins": len(wins),
        "losses": len(losses),
        "lane_results": {r: sum(lane(m).get("result") == r for m in ms) for r in ("won", "even", "lost")},
        "wins_after_lost_lane": sum(lane(m).get("result") == "lost" for m in wins),
        "median_nw_diff_at_10": _med([lane(m).get("nw_diff_at_10") for m in ms]),
        "median_lh_at_10": _med([m["at_10"]["lh"] for m in ms]),
        "median_lh_diff_vs_opponent_at_10": _med(lh_diff),
        "median_deaths_before_10": _med([m["deaths_before_10"] for m in ms]),
        "games_with_death_before_10": sum(m["deaths_before_10"] > 0 for m in ms),
        "median_deaths_before_20_in_wins": _med([m["deaths_before_20"] for m in wins]),
        "median_deaths_before_20_in_losses": _med([m["deaths_before_20"] for m in losses]),
        "heroes": heroes,
    }
