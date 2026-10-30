"""Select objective-specific queued move paths by source and goal."""

from .objective_fork_contract import is_source as owned_fork
from .objective_fork_defense_contract import is_source as owned_fork_defense
from .objective_pawn_contract import is_source as owned_pawn
from .objective_pin_contract import is_source as owned_pin
from .objective_pin_prevent_contract import is_source as owned_pin_prevent
from .objective_promotion_contract import OBJECTIVES


def needs_verification(row):
    return (
        owned_fork(row)
        or owned_fork_defense(row)
        or owned_pawn(row)
        or owned_pin(row)
        or owned_pin_prevent(row)
        or (row["source_type"] == "public" and row["objective"] in OBJECTIVES)
    )


def owned_pin_family(row):
    return owned_pin(row) or owned_pin_prevent(row)
