"""Recognize only current versioned pin kinds and operation contracts."""

from .pin_pipeline import VERSION
from .recurrence_fork_marker import fork_state

PIN_FAMILIES = {
    "pin-execute-mapper": ("pin-execute", VERSION, "pin_execute_opportunity"),
    "pin-prevent-mapper": ("pin-prevent", VERSION, "pin_prevent_opportunity"),
}


def pin_family_ok(row, fact):
    operation = "execute" if row["mapping_producer"] == "pin-execute-mapper" else "prevent"
    return (
        row["mapper_version"] == VERSION
        and row["operation"] == operation
        and row["skill"] in {"absolute_pin", "relative_pin"}
        and fact["payload"].get("kind") == row["skill"]
    )


def marker_state(db, row, fact, parts):
    state = fork_state(db, row, fact, parts)
    if row["mapping_producer"] in PIN_FAMILIES and state == "currentness unverified":
        return "currentness unavailable"
    return state
