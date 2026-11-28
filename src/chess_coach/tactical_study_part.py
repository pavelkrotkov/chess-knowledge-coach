"""Bind one publisher target to the exact qualified parent and its manifest."""

from .course_parts import partition
from .tactical_export_groups import course_groups


def select(course, parent, requested):
    if requested is None:
        return {"course": course, "course_sha256": parent}
    manifest = partition(course_groups(course), parent)
    if not isinstance(requested, dict) or set(requested) != {"number", "sha256", "manifest_sha256"}:
        raise ValueError("course part selection unavailable")
    number = requested["number"]
    if type(number) is not int or not 1 <= number <= manifest["part_count"]:
        raise ValueError("course part selection unavailable")
    part = manifest["parts"][number - 1]
    if requested["manifest_sha256"] != manifest["sha256"] or requested["sha256"] != part["sha256"]:
        raise ValueError("course part changed")
    if manifest["part_count"] < 2:
        raise ValueError("a single course uses its original Study")
    binding = {
        "parent_sha256": parent,
        "manifest_sha256": manifest["sha256"],
        "number": number,
        "count": part["count"],
        "indices": part["indices"],
    }
    body = {key: value for key, value in part.items() if key != "sha256"}
    return {"course": body, "course_sha256": part["sha256"], "multipart": binding}


def delivery_matches(delivery, binding, *, complete=False):
    if not isinstance(delivery, dict) or delivery.get("multipart") != binding:
        return False
    chapters = delivery.get("chapters")
    if not isinstance(chapters, dict):
        return False
    if complete and len(chapters) != len(binding["indices"]):
        return False
    for key, entry in chapters.items():
        if not isinstance(key, str) or not key.isdecimal() or str(int(key)) != key:
            return False
        index = int(key)
        if index >= len(binding["indices"]) or not isinstance(entry, dict):
            return False
        if (entry.get("parent_sha256"), entry.get("original_index")) != (
            binding["parent_sha256"],
            binding["indices"][index],
        ):
            return False
    return True


def receipt(directory, learner, target):
    from .opening_queue_files import read
    from .tactical_study_receipt import exact

    if "multipart" not in target:
        return exact(directory, learner, target["course_sha256"], target["course"])
    path = directory / f"tactical-study-{target['course_sha256']}-intent.json"
    state = read(path)
    if not isinstance(state, dict) or not delivery_matches(
        state.get("tactical_delivery"), target["multipart"], complete=True
    ):
        return None
    return exact(directory, learner, target["course_sha256"], target["course"])
