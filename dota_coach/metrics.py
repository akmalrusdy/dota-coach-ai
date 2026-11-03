"""All numbers are computed here. Pure functions: match JSON in, dict out."""

RUNE_NAMES = {
    "0": "double_damage", "1": "haste", "2": "illusion", "3": "invisibility",
    "4": "regeneration", "5": "bounty", "6": "arcane", "7": "water",
}
CORE_ITEM_MIN_COST = 2000
WON_LANE_NW = 300  # net worth diff at 10:00 that counts as won/lost lane
NW_SAMPLE_MINUTES = (5, 10, 15, 20, 25, 30, 40, 50)


def _at(series, minute):
    """Value at minute mark, or None if the match was shorter / data missing."""
    if not series or minute >= len(series):
        return None
    return series[minute]


def is_parsed(match):
    ps = match.get("players") or []
    return bool(ps) and all(p.get("gold_t") and p.get("lh_t") for p in ps)


def find_player(match, account_id=None, hero_id=None):
    for p in match["players"]:
        if account_id is not None and p.get("account_id") == account_id:
            return p
        if hero_id is not None and p.get("hero_id") == hero_id:
            return p
    return None


def _is_radiant(p):
    return p["player_slot"] < 128


def lane_opponent(match, p):
    """Enemy core in the same lane (highest net worth at 10:00). None if roaming/unknown."""
    if p.get("is_roaming") or not p.get("lane_role"):
        return None
    foes = [
        q for q in match["players"]
        if _is_radiant(q) != _is_radiant(p)
        and q.get("lane_role") == p["lane_role"] and not q.get("is_roaming")
    ]
    foes = [q for q in foes if _at(q["gold_t"], 10) is not None]
    return max(foes, key=lambda q: q["gold_t"][10], default=None)


def death_times(match, p, hero_names):
    """Seconds of each death, taken from enemies' kills_log (key = victim hero name)."""
    name = hero_names.get(p["hero_id"])
    times = [
        k["time"]
        for q in match["players"] if _is_radiant(q) != _is_radiant(p)
        for k in (q.get("kills_log") or []) if k["key"] == name
    ]
    return sorted(times)


def core_item_timings(p, items):
    log = p.get("purchase_log") or []
    # assembling an item also logs its parts at the same second (e.g. kaya + yasha_and_kaya): keep the result only
    parts = {(e["time"], c) for e in log for c in items.get(e["key"], {}).get("components", [])}
    seen, out = set(), []
    for e in log:
        key = e["key"]
        if key in seen or key.startswith("recipe_") or (e["time"], key) in parts:
            continue
        if items.get(key, {}).get("cost", 0) >= CORE_ITEM_MIN_COST:
            seen.add(key)
            out.append({"item": key, "minute": round(e["time"] / 60, 1)})
    return out


def _pct(b, key):
    v = (b or {}).get(key)
    return None if not v else {"value": round(v["raw"], 2), "percentile": round(v["pct"] * 100)}


def compute_metrics(match, player, hero_names, items):
    foe = lane_opponent(match, player)
    team = [q for q in match["players"] if _is_radiant(q) == _is_radiant(player)]
    team_kills = sum(q.get("kills") or 0 for q in team)
    deaths = death_times(match, player, hero_names)

    lane = None
    if foe:
        diff = player["gold_t"][10] - foe["gold_t"][10]
        lane = {
            "opponent_hero": hero_names.get(foe["hero_id"]),
            "nw_diff_at_10": diff,
            "result": "won" if diff >= WON_LANE_NW else "lost" if diff <= -WON_LANE_NW else "even",
        }

    nw_vs_opp = None
    if foe:
        nw_vs_opp = {
            m: player["gold_t"][m] - foe["gold_t"][m]
            for m in NW_SAMPLE_MINUTES
            if _at(player["gold_t"], m) is not None and _at(foe["gold_t"], m) is not None
        }

    runes = {}
    for r in player.get("runes_log") or []:
        n = RUNE_NAMES.get(str(r["key"]), str(r["key"]))
        runes[n] = runes.get(n, 0) + 1

    bench = player.get("benchmarks")
    return {
        "hero": hero_names.get(player["hero_id"]),
        "won": bool(player.get("win")) if "win" in player and player["win"] is not None
        else (match["radiant_win"] == _is_radiant(player)),
        "duration_min": round(match["duration"] / 60, 1),
        "lane_role": player.get("lane_role"),
        "kda": [player.get("kills"), player.get("deaths"), player.get("assists")],
        "at_5": {"lh": _at(player["lh_t"], 5), "dn": _at(player["dn_t"], 5), "xp": _at(player["xp_t"], 5)},
        "at_10": {"lh": _at(player["lh_t"], 10), "dn": _at(player["dn_t"], 10), "xp": _at(player["xp_t"], 10)},
        "lane": lane,
        "lane_efficiency_pct": player.get("lane_efficiency_pct"),
        "runes": runes,
        "gpm": player.get("gold_per_min"),
        "xpm": player.get("xp_per_min"),
        "benchmarks": {
            k: _pct(bench, k)
            for k in ("gold_per_min", "xp_per_min", "last_hits_per_min", "hero_damage_per_min")
        },
        "core_items": core_item_timings(player, items),
        "death_times_sec": deaths,
        "deaths_before_10": sum(t < 600 for t in deaths),
        "deaths_before_20": sum(t < 1200 for t in deaths),
        "nw_diff_vs_lane_opponent": nw_vs_opp,
        "kill_participation_pct": round(100 * ((player.get("kills") or 0) + (player.get("assists") or 0)) / team_kills)
        if team_kills else None,
        "tower_damage": player.get("tower_damage"),
        "buybacks": len(player.get("buyback_log") or []),
    }
