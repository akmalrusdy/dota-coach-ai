from dota_coach.validate import unverified_numbers

M = {
    "gpm": 1263, "duration_min": 20.7,
    "death_times_sec": [474, 744],
    "at_10": {"lh": 29},
    "benchmarks": {"xp_per_min": {"value": 2410.4, "percentile": 87}},
    "nw_diff_vs_lane_opponent": {"5": 1626, "10": -499},
}


def check(text):
    return unverified_numbers(text, M)


def test_real_numbers_pass():
    assert check("GPM 1263 (87th), 20.7 min, 29 LH at 10; NW −499 at 10; XPM 2410") == []


def test_invented_number_flagged():
    assert check("GPM 1263 and 86th percentile") == ["86"]


def test_clock_from_seconds_and_minute_marks():
    assert check("deaths at 7:54 and 12:24, before 20:00") == []
    assert check("death at 9:13") == ["9:13"]


def test_list_markers_headers_and_drill_ignored():
    assert check("**Problems (up to 3)**\n1. GPM 1263\n2. LH 29\n**Drill for next 3 games**\nTarget 4+ runes") == []
    assert check("1. GPM 1263\n**Drill**\nreach 99") == []


def test_thousands_separator():
    assert check("GPM 1,263") == []


def test_percentile_paired_with_wrong_metric_flagged():
    # 86 is a real number elsewhere in real data, but not XPM's percentile
    m = {"benchmarks": {"xp": {"value": 2410, "percentile": 87}, "lh": {"value": 4.15, "percentile": 86}}}
    assert unverified_numbers("XP (2410, 86th) and LH (4.15/min, 86th)", m) == ["2410 -> 86th (actual 87th)"]
    assert unverified_numbers("XP (2410, 87th)", m) == []
