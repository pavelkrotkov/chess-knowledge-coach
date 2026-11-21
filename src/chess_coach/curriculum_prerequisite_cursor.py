"""Validate the signed prerequisite interpretation and source scope."""

from .curriculum_cursor_capture import _digest
from .curriculum_cursor_values import text


def validate_prerequisite(state):
    if not text(state["prerequisite_policy"], 128) or not _digest(state["prerequisite_graph"]):
        raise ValueError("invalid prerequisite policy")
    _binding(state)


def _binding(state):
    checked, offered = state["prerequisite_checked"], state["prerequisite_offered"]
    scope = state["prerequisite_scope"]
    if not all(type(value) is bool for value in (checked, offered, state["prerequisite_deferred"])):
        raise ValueError("invalid prerequisite state")
    if scope is not None and not _digest(scope):
        raise ValueError("invalid prerequisite scope")
    if checked != (scope is not None) or (offered and not checked):
        raise ValueError("invalid prerequisite binding")
