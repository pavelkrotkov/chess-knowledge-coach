"""Validate the shape of an untrusted curriculum cursor."""

from .curriculum_cursor_positions import validate_positions
from .curriculum_cursor_scope import validate_scope

BASE = {
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
VERSION_FIELDS = (
    (2, {"capture_pending"}),
    (3, {"fork_pending", "family_turn", "family_index"}),
    (
        4,
        {
            "prerequisite_policy",
            "prerequisite_graph",
            "prerequisite_scope",
            "prerequisite_checked",
            "prerequisite_offered",
            "prerequisite_deferred",
        },
    ),
)


def validate_state(state) -> None:
    if not isinstance(state, dict) or type(state.get("v")) is not int:
        raise ValueError("invalid cursor fields")
    if state["v"] not in {1, 2, 3, 4, 5}:
        raise ValueError("invalid cursor version")
    fields = set(BASE)
    for minimum, extra in VERSION_FIELDS:
        if state["v"] >= minimum:
            fields.update(extra)
    if state["v"] == 5:
        from .curriculum_public_cursor import fields as public_fields

        fields.update(public_fields())
    if set(state) != fields:
        raise ValueError("invalid cursor fields")
    validate_scope(state)
    validate_positions(state)
