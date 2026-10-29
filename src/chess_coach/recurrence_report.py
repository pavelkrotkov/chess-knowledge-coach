"""Bounded descriptive candidate reports over explicit game-start windows."""

from .recurrence_collect import collect, deduplicate
from .recurrence_page import navigation, select
from .recurrence_report_helpers import target_history, update_coverage
from .recurrence_snapshot import read_snapshot
from .recurrence_sources import games
from .recurrence_summary import summarize
from .recurrence_windows import default_windows as default_windows
from .recurrence_windows import windows


def report(
    db,
    learner,
    start,
    end,
    compare_start,
    *,
    skill=None,
    operation=None,
    cursor=None,
    _history=None,
):
    with read_snapshot(db):
        return _report(
            db,
            learner,
            start,
            end,
            compare_start,
            skill=skill,
            operation=operation,
            cursor=cursor,
            _history=_history,
        )


def _report(db, learner, start, end, compare_start, *, skill, operation, cursor, _history):
    begin, finish, previous = windows(start, end, compare_start)
    pairs, before, history, key = select(
        db, learner, begin, finish, previous, skill, operation, cursor
    )
    if _history is not None:
        target_history(db, learner, pairs, before, _history)
    source, coverage = games(db, learner)
    found, exclusions, limited, cache, recorded, next_before = collect(
        db, learner, source, begin, finish, previous, pairs, before, _history=_history
    )
    selected = deduplicate(found, exclusions)
    update_coverage(coverage, exclusions, limited, cache)
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
