"""Validate the versioned owned-capture continuation binding."""

import re


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def validate_order(pending, prior):
    if pending is not None and prior is not None and pending[:2] <= prior:
        raise ValueError("pending candidate does not follow the corpus position")


def validate_capture(state):
    value = state["capture_pending"]
    if value is not None and not _digest(value):
        raise ValueError("invalid capture binding")
    if state["phase"] != "capture" and value is not None:
        raise ValueError("unexpected capture binding")
    if state["phase"] == "capture" and value is None and state["scheduled_after"] != 0:
        raise ValueError("orphaned capture scan")
