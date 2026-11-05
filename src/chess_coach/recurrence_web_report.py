"""Assemble the bounded landing and source-linked selected reports."""

from .diagnostic_coverage import diagnostic_coverage
from .lesson_narrative import build
from .preview_snapshot import preview_history
from .recurrence_report import report
from .recurrence_snapshot import read_snapshot
from .recurrence_windows import windows


def _attach_lessons(result, db, subject, history):
    for period in ("previous", "current"):
        for group in result[period]:
            group["lesson"] = build(db, subject, group, _history=history)


def landing(db, subject, start, end, previous):
    windows(start, end, previous)
    with read_snapshot(db):
        return diagnostic_coverage(db, subject)


def selected(db, subject, start, end, previous, skill, operation, cursor):
    with read_snapshot(db), preview_history(db, subject) as history:
        result = report(
            db,
            subject,
            start,
            end,
            previous,
            skill=skill,
            operation=operation,
            cursor=cursor,
            _history=history,
        )
        _attach_lessons(result, db, subject, history)
    return result
