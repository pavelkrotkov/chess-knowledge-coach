"""Signed continuation state for the optional public mate opportunity."""

from .curriculum_cursor_capture import _digest
from .curriculum_cursor_coordinates import valid_new
from .curriculum_cursor_values import integer

POLICY = "public-mate-plan-v1-quota-1"
STATUSES = {
    "unchecked",
    "offered",
    "deferred",
    "exhausted",
    "unavailable",
    "learning_unavailable",
    "exposure_unknown",
    "provided",
}


def fields():
    return {
        "public_policy": POLICY,
        "public_after": None,
        "public_pending": None,
        "public_binding": None,
        "public_examined": 0,
        "public_status": "unchecked",
    }


def validate(state):
    if state["public_policy"] != POLICY:
        raise ValueError("public plan policy changed")
    if state["public_status"] not in STATUSES or not integer(
        state["public_examined"], 0, 2**63 - 1
    ):
        raise ValueError("invalid public scan state")
    if state["public_binding"] is not None and not _digest(state["public_binding"]):
        raise ValueError("invalid public offer")
    _position(state)


def _position(state):
    after, pending = state["public_after"], state["public_pending"]
    if not valid_new(after, False):
        raise ValueError("invalid public scan position")
    if pending is None:
        if state["phase"] == "public" and state["scheduled_after"]:
            raise ValueError("orphaned public conflict scan")
        return
    if not _digest(pending) or after is None or state["phase"] != "public":
        raise ValueError("invalid public candidate")
