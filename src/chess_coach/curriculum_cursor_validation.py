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
    if not isinstance(state, dict) or type(state.get("v")) is not int:
        raise ValueError("invalid cursor fields")
    if state["v"] in {2, 3}:
        fields.add("capture_pending")
    if state["v"] == 3:
        fields.update({"fork_pending", "family_turn", "family_index"})
    if state["v"] not in {1, 2, 3} or set(state) != fields:
        raise ValueError("invalid cursor fields")
    validate_scope(state)
    validate_positions(state)
