"""Bounded descriptive candidate reports over explicit game-start windows."""

from datetime import UTC, datetime, timedelta

from .mastery_time import parse_utc
from .recurrence_collect import collect, deduplicate
from .recurrence_page import navigation, select
from .recurrence_snapshot import read_snapshot
from .recurrence_sources import games
from .recurrence_summary import summarize


def windows(start, end, compare_start):
    begin, finish, previous = parse_utc(start), parse_utc(end), parse_utc(compare_start)
    if begin is None or finish is None or previous is None:
        raise ValueError("use timezone-aware compare-start < start < end")
    if not previous < begin < finish:
        raise ValueError("use timezone-aware compare-start < start < end")
    return begin, finish, previous


def default_windows():
    end = datetime.now(UTC)
    return tuple(
        value.isoformat() for value in (end - timedelta(days=30), end, end - timedelta(days=60))
    )


def report(db, learner, start, end, compare_start, *, skill=None, operation=None, cursor=None):
    with read_snapshot(db):
        return _report(
            db, learner, start, end, compare_start, skill=skill, operation=operation, cursor=cursor
        )


def _report(db, learner, start, end, compare_start, *, skill, operation, cursor):
    begin, finish, previous = windows(start, end, compare_start)
    pairs, before, history, key = select(
        db, learner, begin, finish, previous, skill, operation, cursor
    )
    source, coverage = games(db, learner)
    found, exclusions, limited, cache, recorded, next_before = collect(
        db, learner, source, begin, finish, previous, pairs, before
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
        "skill": skill,
        "operation": operation,
        "navigation": navigation(before, history, next_before, key, bool(skill)),
    }
