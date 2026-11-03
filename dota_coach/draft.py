"""Draft scoring. Pure functions; every number the LLM sees is computed here."""
import re

K_MATCHUP = 40   # pseudo-games pulling a thin matchup sample toward the hero's baseline
K_PERSONAL = 30  # same for the player's own record on the hero
MATCHUP_WEIGHT = 0.5  # mid is last pick for both sides: matchup is a tie-breaker, not a driver


def shrink(wins, games, prior, k):
    return (wins + k * prior) / (games + k)


def bracket_record(stat, rank_tier):
    """(wins, picks) in the player's rank bracket (rank_tier // 10), else all pubs."""
    b = (rank_tier or 0) // 10
    if 1 <= b <= 8 and stat.get(f"{b}_pick"):
        return stat[f"{b}_win"], stat[f"{b}_pick"]
    return stat["pub_win"], stat["pub_pick"]


def rank_candidates(candidates, stats, matchups, personal, enemies, rank_tier):
    """Score = bracket win rate + MATCHUP_WEIGHT * mean shrunk matchup edge vs known enemies + shrunk personal edge (pct points)."""
    out = []
    for h in candidates:
        w, p = bracket_record(stats[h], rank_tier)
        base = w / p
        ms = []
        for e in enemies:
            g, wn = matchups.get(h, {}).get(e, (0, 0))
            ms.append({"enemy": e, "games": g, "wins": wn,
                       "edge_pct": round(100 * (shrink(wn, g, base, K_MATCHUP) - base), 1)})
        pg, pw = personal.get(h, (0, 0))
        pe = round(100 * (shrink(pw, pg, base, K_PERSONAL) - base), 1)
        me = round(sum(m["edge_pct"] for m in ms) / len(ms), 1) if ms else 0.0
        out.append({
            "hero": h, "bracket_winrate_pct": round(100 * base, 1), "bracket_picks": p,
            "matchups": ms, "matchup_edge_pct": me,
            "personal_games": pg, "personal_wins": pw, "personal_edge_pct": pe,
            "score": round(100 * base + MATCHUP_WEIGHT * me + pe, 1),
        })
    return sorted(out, key=lambda r: -r["score"])


def hero_sections(notes_md, names):
    """{name: text} for the '## Hero' sections of the local patch-notes file that match `names`."""
    secs = {m.group(1).strip(): m.group(2).strip()
            for m in re.finditer(r"^## ([^\n]+)\n(.*?)(?=^## |\Z)", notes_md, re.M | re.S)}
    return {n: secs[n] for n in names if n in secs}
