"""Validate candidates and retain safe exclusion reasons."""

from .public_training_read import candidates
from .public_training_validate import validate_task


def collect(path, content_format):
    tasks, excluded, ids = [], [], set()
    for number, candidate, reason in candidates(path, content_format):
        key = candidate.get("id") if isinstance(candidate, dict) else None
        if key and key in ids:
            raise ValueError("duplicate task identifier")
        if key:
            ids.add(key)
        try:
            if reason:
                raise ValueError(reason)
            task = validate_task(candidate)
            tasks.append(task)
        except (ValueError, TypeError) as exc:
            excluded.append((number, _exclusion_reason(exc)))
    return tasks, excluded


def _exclusion_reason(exc):
    safe = {
        "unsupported objective",
        "invalid solution lines",
        "malformed PGN",
        "invalid PGN position or lines",
        "invalid task identifier",
    }
    return str(exc) if str(exc) in safe else "invalid prompt or solution line"
