"""Validate recurrence periods and calculate browser defaults."""

from datetime import UTC, datetime, timedelta

from .mastery_time import parse_utc


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
