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


def validate_state(state, *, allow_full=False) -> None:
    if not isinstance(state, dict) or type(state.get("v")) is not int:
        raise ValueError("invalid cursor fields")
    if state["v"] not in {1, 2, 3, 4, 5, 6, 8}:
        raise ValueError("invalid cursor version")
    if set(state) != _fields(state):
        raise ValueError("invalid cursor fields")
    validate_scope(state)
    validate_positions(state, allow_full=allow_full)
    if state["v"] == 8:
        from .curriculum_priority_cursor import validate

        validate(state)


def _fields(state):
    version = state["v"]
    fields = set(BASE)
    for minimum, extra in VERSION_FIELDS:
        if version >= minimum:
            fields.update(extra)
    if version in {5, 6, 8}:
        from .curriculum_public_cursor import fields as public_fields

        fields.update(public_fields())
    if version in {6, 8}:
        from .curriculum_canonical_cursor import fields as canonical_fields

        fields.update(canonical_fields())
    if version == 8:
        fields.update({"priority_policy", "priority_goal", "priority"})
        # The new file-bound policy leaves the prior v8 cursor shape unchanged.
        from .curriculum_priority_cursor import CAPTURE_POLICY

        if state.get("priority_policy") == CAPTURE_POLICY:
            fields.update({"capture_files", "capture_selection"})
    return fields
