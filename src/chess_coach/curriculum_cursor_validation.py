"""Validate the shape of an untrusted curriculum cursor."""

from .curriculum_cursor_positions import validate_positions
from .curriculum_cursor_scope import validate_scope


def validate_state(state) -> None:
    fields = {
        "v",
        "subject_hash",
        "corpus_version",
        "limit",
        "scan_limit",
        "as_of",
        "revision",
        "phase",
        "due_after",
        "new_after",
        "pending",
        "scheduled_after",
        "scheduled_best",
        "seen",
    }
    if (
        not isinstance(state, dict)
        or set(state) != fields
        or type(state["v"]) is not int
        or state["v"] != 1
    ):
        raise ValueError("invalid cursor fields")
    validate_scope(state)
    validate_positions(state)
