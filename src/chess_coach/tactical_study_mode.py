"""Verify one exact tactical chapter identity, mode and Study marker."""

from .study_chapter_modes import chapter_mode
from .study_remote import StudyError
from .tactical_study_order import verify as verify_order


def verify(remote, study, state, chapters, index):
    ids = verify_order(study, state, chapters)
    if index >= len(ids):
        raise StudyError("Study chapter identity is unavailable")
    chapter_mode(
        remote,
        state["study"],
        ids[index],
        chapters[index].get("mode", "conceal"),
        marker=state["marker"],
    )


def require_entry(ids, entry):
    if not ids or entry != ids[0]:
        raise StudyError("Study entry chapter differs")
