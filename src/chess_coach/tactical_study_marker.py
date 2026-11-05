"""Check the opaque Study version marker when one is required."""

from .study_remote import StudyError


def require(study, marker):
    if marker is not None and study.get("name") != marker:
        raise StudyError("Study marker no longer matches the publication intent")
