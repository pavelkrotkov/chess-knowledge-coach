"""Count one direction per game and reject mixed opening contexts."""

from collections import defaultdict

MIN_GAMES = 3


def _unique(rows):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["id"]].append(row)
    good = [items[0] for items in grouped.values() if len({x["choice"] for x in items}) == 1]
    return good, len(grouped) - len(good)


def _positive(unique, mixed, times, played, tied):
    return (
        len(unique) >= MIN_GAMES
        and played == len(unique)
        and not mixed
        and len(times) == 1
        and "unknown" not in times
        and not tied
    )


def summarize(rows):
    unique, mixed = _unique(rows)
    times = {
        row["time_control"] if row["time_control"] not in (None, "", "?", "-") else "unknown"
        for row in unique
    }
    dates = sorted(row["date"] for row in unique)
    played = sum(row["choice"] == "played_capture" for row in unique)
    alternative = sum(row["choice"] == "alternative_capture" for row in unique)
    tied = len(dates) != len(set(dates))
    positive = _positive(unique, mixed, times, played, tied)
    return {
        "games": len(unique),
        "decisions": len(rows),
        "mixed_games": mixed,
        "duplicate_decisions": len(rows) - len({row["id"] for row in rows}),
        "played_capture": played,
        "alternative_capture": alternative,
        "time_control": next(iter(times)) if len(times) == 1 else "mixed",
        "first_start": dates[0] if dates else None,
        "last_start": dates[-1] if dates else None,
        "tied_starts": tied,
        "positive": positive,
    }
