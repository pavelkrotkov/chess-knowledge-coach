"""Validate a persisted played-time key before using it in SQLite."""

from datetime import UTC, datetime


def _timestamp(value):
    try:
        moment = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return False
    return moment.tzinfo == UTC and moment.isoformat() == value and not moment.microsecond


def position(after):
    if after is None:
        return True
    if not isinstance(after, list) or len(after) != 2:
        return False
    return _timestamp(after[0]) and type(after[1]) is int and 0 < after[1] < 2**63
