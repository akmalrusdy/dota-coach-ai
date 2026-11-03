from dota_coach.draft import hero_sections, rank_candidates, shrink

STATS = {
    1: {"pub_pick": 1000, "pub_win": 500, "4_pick": 200, "4_win": 110},  # 55% in bracket 4
    2: {"pub_pick": 1000, "pub_win": 520, "4_pick": 0, "4_win": 0},      # falls back to pubs: 52%
}


def test_shrink_thin_sample_stays_near_prior():
    assert round(shrink(2, 3, 0.5, 40), 3) == 0.512  # 2/3 raw, barely moves


def test_ranking_uses_bracket_and_matchups():
    r = rank_candidates([1, 2], STATS, {2: {9: (100, 70)}}, {}, [9], 40)
    assert [x["hero"] for x in r] in ([1, 2], [2, 1])
    by = {x["hero"]: x for x in r}
    assert by[1]["bracket_winrate_pct"] == 55.0
    assert by[2]["bracket_winrate_pct"] == 52.0
    assert by[2]["matchup_edge_pct"] > 0 and by[1]["matchup_edge_pct"] == 0.0
    assert by[1]["matchups"][0]["games"] == 0


def test_hero_sections():
    md = "# Patch\n\n## Lina\n- Laguna: x\n\n## Items\n- y\n"
    assert hero_sections(md, ["Lina", "Bane"]) == {"Lina": "- Laguna: x"}
