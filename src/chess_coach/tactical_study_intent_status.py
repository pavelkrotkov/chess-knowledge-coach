"""Read a private intent without guessing an interrupted create."""

from .study_remote import StudyError
from .tactical_export_input import _read


def pending(path):
    state = _read(path)
    if (
        not isinstance(state, dict)
        or "study" not in state
        or type(state.get("create_pending")) is not bool
    ):
        raise StudyError("Study intent cannot be verified")
    if state.get("study") is not None and not isinstance(state["study"], str):
        raise StudyError("Study intent cannot be verified")
    return state["create_pending"] and state.get("study") is None
