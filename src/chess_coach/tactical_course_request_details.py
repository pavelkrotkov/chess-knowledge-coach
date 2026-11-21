"""Read recorded coverage for an unsuccessful selected course request."""

from .opening_queue_files import read
from .opening_queue_location import location
from .tactical_course_choice import pairs
from .tactical_course_offer import PREPARE_SLOT
from .tactical_course_request import valid
from .tactical_export_coverage import coverage
from .tactical_export_gaps import omissions


def details(db, root, learner, corpus):
    """Read validated coverage from an unsuccessful selected preparation."""
    try:
        directory, database = location(db, root, learner)
        item = read(directory / PREPARE_SLOT)
        if not valid(item, database, learner, corpus) or item["state"] != "unavailable":
            return None
        chosen = pairs(item["selection"])
        rows, unavailable = item["coverage"], item["unavailable"]
        coverage(rows, chosen)
        omissions(
            {"coverage": rows, "unavailable": unavailable},
            pairs=chosen,
            modern=True,
            owned_deadline=True,
        )
        return {"coverage": rows, "unavailable": unavailable}
    except (OSError, ValueError, TypeError, KeyError):
        return None
