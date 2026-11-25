"""Require a known game-start timestamp that is not in the future."""

from datetime import UTC, datetime

from .mastery_time import parse_utc


def valid(value):
    when = parse_utc(value)
    return when is not None and when <= datetime.now(UTC)
