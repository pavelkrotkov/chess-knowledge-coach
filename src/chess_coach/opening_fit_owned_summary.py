"""Count one direction per game and reject mixed opening contexts."""

import re
from collections import Counter, defaultdict

MIN_GAMES = 3


def _unique(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["id"]].append(row)
    good = [items[0] for items in grouped.values() if len({x["choice"] for x in items}) == 1]
    return good, len(grouped) - len(good), len(rows) - len(grouped)


def _positive(unique, mixed, times, played, tied):
    return (
        len(unique) >= MIN_GAMES
        and played == len(unique)
        and not mixed
        and len(times) == 1
        and "unknown" not in times
        and not tied
    )


def _control(value):
    return (
        value
        if isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*\+(0|[1-9][0-9]*)", value)
        else "unknown"
    )


def summarize(rows):
    unique, mixed, duplicates = _unique(rows)
    times = {_control(row["time_control"]) for row in unique}
    dates = sorted(row["date"] for row in unique) or [None]
    counts = Counter(row["choice"] for row in unique)
    played, alternative = counts["played_capture"], counts["alternative_capture"]
    tied = len(dates) != len(set(dates))
    first, last = dates[0], dates[-1]
    positive = _positive(unique, mixed, times, played, tied)
    return {
        "games": len(unique),
        "decisions": len(rows),
        "mixed_games": mixed,
        "duplicate_decisions": duplicates,
        "played_capture": played,
        "alternative_capture": alternative,
        "time_control": next(iter(times)) if len(times) == 1 else "mixed",
        "first_start": first,
        "last_start": last,
        "tied_starts": tied,
        "positive": positive,
    }
