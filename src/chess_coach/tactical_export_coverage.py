"""Validate the recorded scan coverage without inventing missing sources."""

from .tactical_course_selection import PAIRS, PER_PAIR


def _completed(row):
    return (
        type(row["examined"]) is int
        and 0 <= row["examined"] <= PER_PAIR
        and type(row["limited"]) is bool
        and isinstance(row["excluded"], dict)
    )


def _deferred(row):
    return row["examined"] is None and row["limited"] is True and row["excluded"] == {}


def _valid(row):
    return (row["status"] == "complete" and _completed(row)) or (
        row["status"] == "deferred: time budget" and _deferred(row)
    )


def coverage(rows):
    if not isinstance(rows, list) or len(rows) != len(PAIRS):
        raise ValueError("invalid preview coverage")
    for row, (skill, operation) in zip(rows, PAIRS, strict=True):
        if (row["skill"], row["operation"]) != (skill, operation) or not _valid(row):
            raise ValueError("preview coverage differs")
