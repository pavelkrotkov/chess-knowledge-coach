"""Validate and fingerprint a training submission."""

from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity


def validate_request(
    attempt_id: str, event_id: str, move: str, item_id: int, subject: str
) -> tuple[str, str]:
    normalized = normalize_identity(subject) if isinstance(subject, str) else None
    if normalized is None:
        raise ValueError("an explicit learner subject is required")
    if not all(isinstance(value, str) and value for value in (attempt_id, event_id, move)):
        raise ValueError("attempt ID, event ID, and move are required")
    if type(item_id) is not int or item_id < 1:
        raise ValueError("training item ID must be a positive integer")
    data = {
        "attempt_id": attempt_id,
        "event_id": event_id,
        "move": move,
        "item_id": item_id,
        "subject": normalized,
    }
    return normalized, digest(canonical(data))
