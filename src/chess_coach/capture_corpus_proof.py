"""Qualify one indexed corpus candidate with the existing bounded verifiers."""

from .capture_public_proof import qualify as public_qualify
from .puzzle_session_validate import validate_line
from .related_capture_assessment import certificate
from .related_capture_features import _shape, inspect_shape


def _features(candidate, check):
    try:
        prompt = validate_line(candidate["fen"], candidate["solution"])
        shape = _shape(prompt, candidate["solution"].split()[1:])
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
            None,
            "unsupported",
            "recapture_or_sacrifice",
            "special_capture",
            "pawn_capture_outside_coverage",
            "exchange_unresolved",
        }
        if reason not in known:
            entry.update(state="unresolved", reason=reason)
        else:
            entry.update(
                feature=feature, state="assessment" if feature else "complete", reason=reason
            )
        return used
    try:
        entry["assessment"] = certificate(db, candidate["version"], candidate["key"], check=check)
    except (ValueError, TypeError, KeyError, IndexError):
        entry["assessment"] = None
    entry["state"] = "complete"
    return 1


def prepare(db, entry, check):
    if entry["state"] == "interrupted":
        return 0
    try:
        if entry["candidate"]["type"] == "public":
            return public_qualify(db, entry, check)
        return _qualify(db, entry, check)
    except TimeoutError:
        entry["state"] = "interrupted"
        raise
