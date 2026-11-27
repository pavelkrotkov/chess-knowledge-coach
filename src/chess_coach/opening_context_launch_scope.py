"""Bind selected context to the exact goal and wall-clock window."""

from .curriculum_window_cursor import decode
from .fact_fingerprint import canonical, digest


def _scope(window):
    return digest(canonical([window["goal"], window["issued_at"], window["expires_at"]]))


def result(plan):
    window = plan.get("window")
    return digest(canonical(None)) if window is None else _scope(window)


def cursor(db, value, owner):
    try:
        window = decode(db, value)
    except ValueError:
        from .curriculum_cursor_codec import decode_cursor

        decode_cursor(db, value)
        return digest(canonical(None))
    if window["selection_only"] or window["state"]["subject_hash"] != owner:
        raise ValueError("practice window scope changed")
    return _scope(window)


def common_offer(data, window, owner):
    from .curriculum_priority_cursor import COMMON_POLICY
    from .curriculum_window_policy import check_window

    check_window(window)
    state = window["state"]
    if (
        window["selection_only"]
        or state["subject_hash"] != owner
        or state.get("priority_policy") != COMMON_POLICY
        or data[1:4] != [owner, window["goal"], window["expires_at"]]
    ):
        raise ValueError("practice window changed")
    expected = {
        "revision": state["revision"],
        "common_input": state["common_input"],
        "corpus_version": state["corpus_version"],
        "as_of": state["as_of"],
        "window_scope": _scope(window),
    }
    if data[7] != expected:
        raise ValueError("practice window changed")
