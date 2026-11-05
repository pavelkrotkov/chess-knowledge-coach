"""Recheck tactical privacy, ordered inventory and content before the receipt."""

from .study_anonymous import verify as verify_private
from .study_inventory import named
from .study_privacy import metadata
from .study_remote import StudyError
from .tactical_study_order import verify


def check(remote, state, chapters, ids, match):
    verify_private(remote, state["study"])
    study = metadata(remote, state["study"])
    if verify(study, state, chapters, complete=True) != ids:
        raise StudyError("Study chapter identity changed")
    exported = remote.export(state["study"])
    if not all(match(named(chapter, state, i), exported) for i, chapter in enumerate(chapters)):
        raise StudyError("Study read-back is incomplete")
    study = metadata(remote, state["study"])
    if verify(study, state, chapters, complete=True) != ids:
        raise StudyError("Study chapter identity changed")
