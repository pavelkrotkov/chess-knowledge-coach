"""Select objective-specific queued move paths by source and goal."""

from .objective_fork_contract import is_source as owned_fork
from .objective_pawn_contract import is_source as owned_pawn
from .objective_promotion_contract import OBJECTIVES


def needs_verification(row):
    return (
        owned_fork(row)
        or owned_pawn(row)
        or (row["source_type"] == "public" and row["objective"] in OBJECTIVES)
    )
