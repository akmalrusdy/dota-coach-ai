from dota_coach.trend import summarize


def m(won, lane, nw, lh, opp_lh, d10, d20, hero="npc_dota_hero_lina"):
    return {"won": won, "hero": hero, "at_10": {"lh": lh}, "deaths_before_10": d10, "deaths_before_20": d20,
            "lane": {"result": lane, "nw_diff_at_10": nw, "opponent_lh_at_10": opp_lh}}


MS = [
    m(True, "lost", -600, 40, 45, 0, 2),
    m(True, "won", 700, 44, 40, 0, 1),
    m(False, "lost", -1000, 38, 44, 1, 5),
    m(False, "even", 100, 36, 36, 0, 3),
]


def test_summarize():
    s = summarize(MS)
    assert (s["matches"], s["wins"], s["losses"]) == (4, 2, 2)
    assert s["lane_results"] == {"won": 1, "even": 1, "lost": 2}
    assert s["wins_after_lost_lane"] == 1
    assert s["median_nw_diff_at_10"] == -250.0
    assert s["median_lh_diff_vs_opponent_at_10"] == -2.5  # diffs: -5, 4, -6, 0
    assert s["median_deaths_before_20_in_wins"] == 1.5
    assert s["median_deaths_before_20_in_losses"] == 4.0
    assert s["games_with_death_before_10"] == 1
    assert s["heroes"] == {"lina": {"games": 4, "wins": 2}}


def test_missing_lane_data_does_not_crash():
    x = m(True, None, None, None, None, 0, 0)
    x["lane"] = None
    s = summarize([x])
    assert s["median_nw_diff_at_10"] is None and s["median_lh_diff_vs_opponent_at_10"] is None


def test_by_opponent_groups_and_orders():
    from dota_coach.trend import by_opponent
    a = [m(True, "won", 700, 44, 40, 0, 1), m(False, "lost", -600, 30, 40, 1, 2), m(False, "lost", -800, 32, 40, 2, 3)]
    for x in a[:2]:
        x["lane"]["opponent_hero"] = "npc_dota_hero_death_prophet"
    a[2]["lane"]["opponent_hero"] = "npc_dota_hero_pudge"
    r = by_opponent(a)
    assert list(r) == ["npc_dota_hero_death_prophet", "npc_dota_hero_pudge"]
    assert r["npc_dota_hero_death_prophet"]["games"] == 2 and r["npc_dota_hero_death_prophet"]["wins"] == 1
    assert r["npc_dota_hero_death_prophet"]["lane_results"] == {"won": 1, "even": 0, "lost": 1}
