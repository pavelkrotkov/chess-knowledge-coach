"""Bind and qualify exact licensed public capture examples in the worker."""

from .capture_public_index import bind
from .related_capture_features import _shape, inspect_shape


def qualify(db, entry, check):
    candidate = entry["candidate"]
    used = 0
    try:
        if bind(db, candidate["version"], candidate["key"], check) != (
            entry["identity"],
            candidate,
        ):
            raise ValueError("public capture changed")
        shape = _shape(candidate["fen"], candidate["line"].split())
        if shape is None:
            entry.update(feature=None, state="complete", reason="unsupported")
            return 0
        used = 1
        feature, reason = inspect_shape(shape, check=check)
        check()
        if bind(db, candidate["version"], candidate["key"], check) != (
            entry["identity"],
            candidate,
        ):
            raise ValueError("public capture changed")
        known = {"recapture_or_sacrifice", "special_capture", "pawn_capture_outside_coverage"}
        if reason is not None and reason not in known | {"exchange_unresolved"}:
            entry.update(state="unresolved", reason=reason)
        else:
            entry.update(feature=feature, state="complete", reason=reason)
        return used
    except (ValueError, TypeError, KeyError, IndexError):
        entry.update(state="unresolved", reason="source_unavailable")
        return used
