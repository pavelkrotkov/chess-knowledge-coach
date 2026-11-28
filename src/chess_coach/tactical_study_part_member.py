"""Rebind one persisted part delivery to its owner-bound retained parent."""

from .tactical_export_input import load
from .tactical_exposure_pointer import pointer
from .tactical_study_part import delivery_matches, select
from .tactical_study_preview import preview


def member(root, directory, database, subject, parent, state):
    delivery = state.get("tactical_delivery")
    if not isinstance(delivery, dict):
        return False
    binding = delivery.get("multipart")
    if not isinstance(binding, dict) or binding.get("parent_sha256") != parent:
        return False
    path = pointer(directory, database, subject, parent)
    if path is None:
        return False
    envelope = load(root, path)
    preview(envelope, parent)
    requested = {
        "number": binding.get("number"),
        "sha256": state.get("course_sha256"),
        "manifest_sha256": binding.get("manifest_sha256"),
    }
    try:
        target = select(envelope["export"], parent, requested)
    except (ValueError, KeyError, TypeError, IndexError):
        return False
    return delivery_matches(delivery, target["multipart"])
