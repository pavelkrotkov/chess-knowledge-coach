"""Verify the exact signed window used by a selected opening launch."""

from .curriculum_prerequisite_token import _decode
from .curriculum_window_cursor import decode
from .curriculum_window_scope import POLICY
from .fact_fingerprint import canonical, digest
from .opening_context_launch_scope import _scope


def _check(data, window, owner):
    if data[:2] != [POLICY, owner]:
        raise ValueError("practice window changed")
    if window["selection_only"] or window["state"]["subject_hash"] != owner:
        raise ValueError("practice window changed")
    if (data[2], data[3], data[7]) != (
        window["goal"],
        window["expires_at"],
        window["state"]["revision"],
    ):
        raise ValueError("practice window changed")


def offer(db, value, window_cursor, owner):
    if value is None and window_cursor is None:
        return digest(canonical(None))
    if value is None or window_cursor is None:
        raise ValueError("practice window changed")
    data = _decode(db, value)
    window = decode(db, window_cursor)
    _check(data, window, owner)
    return _scope(window)
