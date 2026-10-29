"""Bounded descriptive candidate reports over explicit game-start windows."""

from datetime import UTC, datetime, timedelta

from .mastery_time import parse_utc
from .recurrence_collect import collect, deduplicate
from .recurrence_sources import games
from .recurrence_summary import summarize


def windows(start, end, compare_start):
    values = [parse_utc(value) for value in (start, end, compare_start)]
    if any(value is None for value in values) or not values[2] < values[0] < values[1]:
        raise ValueError("use timezone-aware compare-start < start < end")
    return values


def default_windows():
    end = datetime.now(UTC)
    return tuple(
        value.isoformat() for value in (end - timedelta(days=30), end, end - timedelta(days=60))
    )


def report(db, learner, start, end, compare_start):
    begin, finish, previous = windows(start, end, compare_start)
    source, coverage = games(db, learner)
    found, exclusions, limited, cache, recorded = collect(
        db, learner, source, begin, finish, previous
    )
    selected = deduplicate(found, exclusions)
    coverage.update(
        {
            "excluded": dict(exclusions),
            "evidence_limits_reached": limited,
            "replayed_games": len(cache),
            "sampled_decisions": sum(
                sum(bool(d["subject"]) for d in g["decisions"].values())
                for g in cache.values()
                if g
            ),
        }
    )
    return {
        "current": summarize([i for i in selected if i["period"] == "current"]),
        "previous": summarize([i for i in selected if i["period"] == "previous"]),
        "start": begin.isoformat(),
        "end": finish.isoformat(),
        "compare_start": previous.isoformat(),
        "coverage": coverage,
        "recorded_mappings": recorded,
    }
