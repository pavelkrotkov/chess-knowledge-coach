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
    if state["v"] in {2, 3, 4}:
        fields.add("capture_pending")
    if state["v"] in {3, 4}:
        fields.update({"fork_pending", "family_turn", "family_index"})
    if state["v"] == 4:
        fields.update(
            {
                "prerequisite_policy",
                "prerequisite_graph",
                "prerequisite_scope",
                "prerequisite_checked",
                "prerequisite_offered",
                "prerequisite_deferred",
            }
        )
    if state["v"] not in {1, 2, 3, 4} or set(state) != fields:
        raise ValueError("invalid cursor fields")
    validate_scope(state)
    validate_positions(state)
