"""Validate daily plan bounds, learner identity, and UTC time."""

from datetime import datetime

from .learner_identity import normalize_identity
from .mastery_time import as_utc


def validate_plan_request(
    subject: str, corpus_version: str, limit: int, scan_limit: int, as_of: datetime | None
) -> tuple[str, datetime]:
    learner = normalize_identity(subject) if isinstance(subject, str) else None
    if learner is None:
        raise ValueError("an explicit learner subject is required")
    if not isinstance(corpus_version, str) or not corpus_version.strip():
        raise ValueError("corpus version is required")
    _bounds(limit, scan_limit)
    return learner, as_utc(as_of)


def _bounds(limit: int, scan_limit: int) -> None:
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit must be 1..50")
    if type(scan_limit) is not int or not 1 <= scan_limit <= 1000:
        raise ValueError("scan_limit must be 1..1000")
