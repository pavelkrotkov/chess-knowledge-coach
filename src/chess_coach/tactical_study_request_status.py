"""Show only the exact local request and verified private receipt."""

from .opening_queue_files import read
from .opening_queue_location import location
from .tactical_study_part import receipt as part_receipt
from .tactical_study_part import select
from .tactical_study_request import SLOT, configured
from .tactical_study_slot import valid


def status(db, root, learner, corpus, offer, course):
    try:
        directory, database = location(db, root, learner)
        version = offer["hash"]
        item = read(directory / SLOT)
        state = None
        if valid(item, database, learner):
            if item["version"] == version:
                state = item["state"]
            elif item["state"] in {"queued", "incomplete", "stale"}:
                previous = (
                    item["part"]["sha256"] if item.get("part") is not None else item["version"]
                )
                earlier = read(directory / f"tactical-study-{previous}-intent.json")
                if earlier is not None and (
                    not isinstance(earlier, dict) or earlier.get("complete") is not True
                ):
                    state = "blocked"
        part = (
            item.get("part")
            if valid(item, database, learner) and item["version"] == version
            else None
        )
        receipt = part_receipt(directory, learner, select(course, version, part))
        return {
            "state": state,
            "receipt": receipt,
            "part": part,
            "configured": configured(root, db, learner, corpus, version),
        }
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError):
        return {"state": "unavailable", "receipt": None, "configured": False}
