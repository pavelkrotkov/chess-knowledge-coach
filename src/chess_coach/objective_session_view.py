"""Add current objective verification status to the private session view."""

from .objective_pawn_view import display as display_pawn
from .objective_promotion_contract import OBJECTIVES as PROMOTION_OBJECTIVES
from .objective_promotion_routing import owned_pawn
from .objective_promotion_status_policy import enabled
from .objective_promotion_view import display as display_promotion
from .objective_short_continue import continuation
from .objective_short_source import VERSION as SHORT_VERSION
from .objective_status import latest
from .unified_session_state import view


def display(db, row):
    result = view(row)
    if enabled(row):
        result["verification"] = latest(db, row)
    if row["source_type"] == "public" and row["objective"] in PROMOTION_OBJECTIVES:
        display_promotion(db, row, result)
    if owned_pawn(row):
        display_pawn(db, row, result)
    if row["source_version"] == SHORT_VERSION:
        resumed = continuation(db, row)
        if resumed:
            result["fen"] = resumed["board"].fen()
            result["status"] = "objective_verified" if resumed["complete"] else "active"
            result["proved_continuation"] = not resumed["complete"]
    return result
