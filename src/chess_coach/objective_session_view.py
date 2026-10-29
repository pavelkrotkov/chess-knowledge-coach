"""Add current objective verification status to the private session view."""

from .objective_capture_contract import VERSIONS as CAPTURE_VERSIONS
from .objective_contract import VERSION
from .objective_defense_source import VERSION as DEFENSE_VERSION
from .objective_pawn_contract import is_source as pawn_source
from .objective_pawn_view import display as display_pawn
from .objective_protection_contract import VERSION as PROTECTION_VERSION
from .objective_short_continue import continuation
from .objective_short_source import VERSION as SHORT_VERSION
from .objective_status import latest
from .unified_session_state import view


def display(db, row):
    result = view(row)
    if _enabled(row):
        result["verification"] = latest(db, row)
    if pawn_source(row):
        display_pawn(db, row, result)
    if row["source_version"] == SHORT_VERSION:
        resumed = continuation(db, row)
        if resumed:
            result["fen"] = resumed["board"].fen()
            result["status"] = "objective_verified" if resumed["complete"] else "active"
            result["proved_continuation"] = not resumed["complete"]
    return result


def _enabled(row):
    return (
        row["source_type"] == "own-game"
        and (
            pawn_source(row)
            or row["source_version"]
            in {
                VERSION,
                SHORT_VERSION,
                DEFENSE_VERSION,
                PROTECTION_VERSION,
                *CAPTURE_VERSIONS,
            }
        )
        and row["status"] == "needs_verification"
    )
