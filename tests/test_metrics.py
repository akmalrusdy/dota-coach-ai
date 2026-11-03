import json
from pathlib import Path

import pytest

from dota_coach import metrics

D = Path(__file__).parent
MATCH = json.loads((D / "sample_match.json").read_text())
HEROES = {h["id"]: h["name"] for h in json.loads((D / "heroes.json").read_text())}
ITEMS = json.loads((D / "items.json").read_text())

# mid on both sides: slot 1 (Radiant, hero 14) vs slot 131 (Dire, hero 106)
MID = metrics.find_player(MATCH, hero_id=14)
M = metrics.compute_metrics(MATCH, MID, HEROES, ITEMS)


def test_parsed():
    assert metrics.is_parsed(MATCH)
    assert not metrics.is_parsed({"players": [{"gold_t": None, "lh_t": None}]})


def test_cs_and_xp_come_from_series():
    assert M["at_10"]["lh"] == MID["lh_t"][10]
    assert M["at_5"]["dn"] == MID["dn_t"][5]
    assert M["at_10"]["xp"] == MID["xp_t"][10]


def test_lane_opponent_and_result():
    foe = metrics.lane_opponent(MATCH, MID)
    assert foe["hero_id"] == 106
    diff = MID["gold_t"][10] - foe["gold_t"][10]
    assert M["lane"]["nw_diff_at_10"] == diff
    expected = "won" if diff >= 300 else "lost" if diff <= -300 else "even"
    assert M["lane"]["result"] == expected


def test_deaths_match_scoreboard_and_buckets():
    times = M["death_times_sec"]
    assert len(times) == MID["deaths"]
    assert times == sorted(times)
    assert M["deaths_before_10"] == sum(t < 600 for t in times)
    assert M["deaths_before_20"] >= M["deaths_before_10"]


def test_core_items_are_expensive_unique_and_ordered():
    items = M["core_items"]
    names = [i["item"] for i in items]
    assert len(names) == len(set(names))
    assert all(ITEMS[n]["cost"] >= 2000 for n in names)
    assert [i["minute"] for i in items] == sorted(i["minute"] for i in items)


def test_runes_counted():
    assert sum(M["runes"].values()) == len(MID["runes_log"])


def test_kill_participation():
    team = [p for p in MATCH["players"] if (p["player_slot"] < 128) == (MID["player_slot"] < 128)]
    tk = sum(p["kills"] for p in team)
    assert M["kill_participation_pct"] == round(100 * (MID["kills"] + MID["assists"]) / tk)


def test_short_match_gives_none_not_crash():
    assert metrics._at([1, 2, 3], 10) is None
    assert metrics._at(None, 5) is None


def test_json_serialisable():
    json.dumps(M)


def test_combined_item_not_double_counted():
    p = {"purchase_log": [
        {"time": 1439, "key": "yasha"},
        {"time": 1856, "key": "kaya"},
        {"time": 1856, "key": "yasha_and_kaya"},
    ]}
    assert [i["item"] for i in metrics.core_item_timings(p, ITEMS)] == ["yasha", "yasha_and_kaya"]
