"""Add current objective verification status to the private session view."""

from .objective_capture_contract import VERSIONS as CAPTURE_VERSIONS
from .objective_contract import VERSION
from .objective_defense_source import VERSION as DEFENSE_VERSION
from .objective_short_continue import continuation
from .objective_short_source import VERSION as SHORT_VERSION
from .objective_status import latest
from .unified_session_state import view


def display(db, row):
    result = view(row)
    if (
        row["source_version"] in {VERSION, SHORT_VERSION, DEFENSE_VERSION, *CAPTURE_VERSIONS}
        and row["status"] == "needs_verification"
    ):
        result["verification"] = latest(db, row)
    if row["source_version"] == SHORT_VERSION:
        resumed = continuation(db, row)
        if resumed:
            result["fen"] = resumed["board"].fen()
            result["status"] = "objective_verified" if resumed["complete"] else "active"
            result["proved_continuation"] = not resumed["complete"]
    return result
