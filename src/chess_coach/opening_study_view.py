"""Show local status for the exact selected private opening course."""

from .opening_queue_files import read
from .opening_queue_location import location
from .opening_study_receipt import link
from .opening_study_request import SLOT, credentials, valid
from .opening_unfamiliar_legacy import retained


def status(db, root, learner, course):
    try:
        directory, database = location(db, root, learner)
        available = credentials(root, db, learner, course["version"])
        receipt = link(directory, learner, course)
        item = read(directory / SLOT)
        if receipt:
            message = "This private Study was verified."
        elif (
            valid(item, database, learner)
            and item["version"] == course["version"]
            and item["selection"] == course["selection"]
        ):
            message = {
                "queued": "Publication is queued.",
                "incomplete": "Publication is incomplete.",
                "stale": "The requested preview changed. Request a current preview.",
                "complete": "The publication receipt could not be checked.",
            }[item["state"]]
        elif not available:
            message = "Add Study credentials to request publication."
        else:
            message = "This exact course has not been requested."
        return {
            "credentials": available,
            "link": receipt,
            "message": message,
            "request_allowed": not course.get("historical") or retained(directory, course),
        }
    except Exception:
        return {"credentials": False, "link": None, "message": "Study status is unavailable."}
