"""Check that numbers in the LLM's text exist in the metrics it was given."""
import re

NUM = re.compile(r"\d+(?:\.\d+)?")
CLOCK = re.compile(r"\b(\d{1,3}):(\d{2})\b")
HEADER = re.compile(r"^\*\*[^*\n]*\*\*\s*$", re.M)
LIST_MARK = re.compile(r"^\s*\d+\.\s", re.M)


def _leaves(x):
    """Every number in the metrics: values, plus digits in keys (at_5, '10', before_20)."""
    if isinstance(x, dict):
        for k, v in x.items():
            yield from (float(n) for n in NUM.findall(str(k)))
            yield from _leaves(v)
    elif isinstance(x, (list, tuple)):
        for v in x:
            yield from _leaves(v)
    elif isinstance(x, (int, float)) and not isinstance(x, bool):
        yield abs(float(x))
    elif isinstance(x, str):  # e.g. patch-note text: numbers quoted from it are grounded
        yield from (float(n) for n in NUM.findall(x))


def _allowed(metrics):
    vals = set(_leaves(metrics))
    # rounding a metric (493.25 -> 493) is not an invented number
    return {round(v, 2) for v in vals} | {round(v, 1) for v in vals} | {float(round(v)) for v in vals}


PAIR = re.compile(r"(\d+(?:\.\d+)?)[^\d\n]{0,12}?(\d+)(?:st|nd|rd|th)\b")


def _bench_pairs(metrics):
    """{(value, percentile)} from metrics['benchmarks']."""
    return {
        (b["value"], b["percentile"])
        for b in (metrics.get("benchmarks") or {}).values() if b
    }


def wrong_percentiles(text, metrics):
    """'2410, 86th' where 2410 is a benchmark value whose percentile is not 86."""
    pairs = _bench_pairs(metrics)
    out = []
    for val, pct in PAIR.findall(text):
        match = [p for v, p in pairs if round(float(val), 2) in (round(v, 2), round(v, 1), float(round(v)))]
        if match and int(pct) not in match:
            out.append(f"{val} -> {pct}th (actual {match[0]}th)")
    return out


def unverified_numbers(advice, metrics):
    """Numbers in Summary/Problems that are not in metrics. Drill is skipped: its targets are new numbers."""
    text = advice.split("**Drill")[0]
    text = HEADER.sub("", text)
    text = LIST_MARK.sub("", text)
    text = re.sub(r"(?<=\d),(?=\d{3})", "", text)
    bad = wrong_percentiles(text, metrics)
    allowed = _allowed(metrics)
    secs = {v for v in allowed if v == int(v)}
    for m, s in CLOCK.findall(text):
        total = int(m) * 60 + int(s)
        if s != "00" and float(total) not in secs:
            bad.append(f"{m}:{s}")
    text = CLOCK.sub(" ", text)
    bad += [n for n in NUM.findall(text) if round(float(n), 2) not in allowed]
    return list(dict.fromkeys(bad))
