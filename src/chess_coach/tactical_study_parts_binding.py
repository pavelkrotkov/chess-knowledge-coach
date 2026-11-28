"""Verify a Study part against its owner-bound retained parent export."""

from .tactical_export_input import load
from .tactical_exposure_pointer import pointer
from .tactical_study_parts import manifest, target
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
    parts = manifest(envelope["export"], parent)
    number = binding.get("number")
    if type(number) is not int or not 1 <= number <= len(parts["parts"]):
        return False
    expected = target(parts["parts"][number - 1], parts["sha256"])
    if binding != expected["multipart"] or state.get("course_sha256") != expected["course_sha256"]:
        return False
    chapters = delivery.get("chapters")
    if not isinstance(chapters, dict):
        return False
    for key, entry in chapters.items():
        if not isinstance(key, str) or not key.isdecimal() or str(int(key)) != key:
            return False
        index = int(key)
        if index >= len(binding["indices"]) or not isinstance(entry, dict):
            return False
        if (entry.get("parent_sha256"), entry.get("original_index")) != (
            parent,
            binding["indices"][index],
        ):
            return False
    return True
