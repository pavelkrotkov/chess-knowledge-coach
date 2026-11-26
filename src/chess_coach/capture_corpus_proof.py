"""Qualify one indexed corpus candidate with the existing bounded verifiers."""

from .puzzle_session_validate import validate_line
from .related_capture_assessment import certificate
from .related_capture_features import _shape, inspect_shape


def _features(candidate, check):
    try:
        prompt = validate_line(candidate["fen"], candidate["solution"])
        line = candidate["solution"].split()[1:]
        shape = _shape(prompt, line)
        if shape is None:
            return None, "unsupported", 0
        feature, reason = inspect_shape(shape, check=check)
        return feature, reason, 1
    except ValueError:
        return None, "unsupported", 0


def _qualify(db, entry, check):
    candidate = entry["candidate"]
    if entry["state"] == "feature":
        feature, reason, used = _features(candidate, check)
        known = {
            "unsupported",
            "recapture_or_sacrifice",
            "special_capture",
            "pawn_capture_outside_coverage",
        }
        if reason == "exchange_unresolved":
            entry.update(feature=None, state="complete", reason=reason)
        elif reason is not None and reason not in known:
            entry.update(state="unresolved", reason=reason)
        else:
            entry.update(feature=feature, state="assessment" if feature else "complete")
        return used
    try:
        entry["assessment"] = certificate(db, candidate["version"], candidate["key"], check=check)
    except (ValueError, TypeError, KeyError, IndexError):
        entry["assessment"] = None
    entry["state"] = "complete"
    return 1


def prepare(db, entry, check):
    try:
        return _qualify(db, entry, check)
    except TimeoutError:
        entry["state"] = "interrupted"
        raise
