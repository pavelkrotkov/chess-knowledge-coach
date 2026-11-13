"""Show local status for the exact selected private opening course."""

from .opening_queue_files import read
from .opening_queue_location import location
from .opening_study_receipt import link, verified
from .opening_study_request import SLOT, credentials, valid
from .opening_unfamiliar_legacy import retained


def _message(item, database, learner, course, selected, receipt, available):
    if receipt:
        return "This private Study was verified."
    if (
        valid(item, database, learner)
        and item["version"] == course["version"]
        and item["selection"] == selected
    ):
        return {
            "queued": "Publication is queued.",
            "incomplete": "Publication is incomplete.",
            "stale": "The requested preview changed. Request a current preview.",
            "complete": "The publication receipt could not be checked.",
        }[item["state"]]
    if not available:
        return "Add Study credentials to request publication."
    return "This exact course has not been requested."


def status(db, root, learner, course, *, revision=None, selection=None):
    try:
        directory, database = location(db, root, learner)
        available = credentials(root, db, learner, course["version"])
        receipt = (
            verified(directory, learner, course["version"], revision)
            if revision is not None
            else link(directory, learner, course)
        )
        selected = selection if revision is not None else course["selection"]
        item = read(directory / SLOT)
        message = _message(item, database, learner, course, selected, receipt, available)
        return {
            "credentials": available,
            "link": receipt,
            "message": message,
            "request_allowed": not course.get("historical") or retained(directory, course),
        }
    except Exception:
        return {"credentials": False, "link": None, "message": "Study status is unavailable."}
