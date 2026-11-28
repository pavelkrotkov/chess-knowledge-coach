"""Derive exact private Study parts from one already-qualified parent export."""

from .course_parts import partition
from .opening_queue_files import read
from .tactical_export_groups import course_groups
from .tactical_study_receipt import exact


def manifest(course, parent):
    return partition(course_groups(course), parent)


def target(part, manifest_hash):
    body = {key: value for key, value in part.items() if key != "sha256"}
    return {
        "course": body,
        "course_sha256": part["sha256"],
        "multipart": {
            "parent_sha256": part["parent_sha256"],
            "manifest_sha256": manifest_hash,
            "number": part["number"],
            "count": part["count"],
            "indices": part["indices"],
        },
    }


def receipts(directory, learner, value):
    result = []
    for part in value["parts"]:
        course = target(part, value["sha256"])
        path = directory / f"tactical-study-{part['sha256']}-intent.json"
        state = read(path)
        receipt = None
        delivery = state.get("tactical_delivery") if isinstance(state, dict) else None
        if isinstance(delivery, dict) and delivery.get("multipart") == course["multipart"]:
            receipt = exact(directory, learner, part["sha256"], part)
        status = "verified" if receipt else "incomplete" if state is not None else "not started"
        result.append({"number": part["number"], "receipt": receipt, "state": status})
    return result
