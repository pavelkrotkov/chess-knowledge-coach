"""Identify source-scoped sessions with verification status."""

from .objective_capture_contract import VERSIONS as CAPTURE_VERSIONS
from .objective_contract import VERSION
from .objective_defense_source import VERSION as DEFENSE_VERSION
from .objective_fork_contract import is_source as owned_fork
from .objective_promotion_contract import OBJECTIVES as PROMOTION_OBJECTIVES
from .objective_promotion_routing import owned_pawn, owned_pin
from .objective_protection_contract import VERSION as PROTECTION_VERSION
from .objective_short_source import VERSION as SHORT_VERSION


def enabled(row):
    return (
        (row["source_type"] == "public" and row["objective"] in PROMOTION_OBJECTIVES)
        or owned_pawn(row)
        or owned_fork(row)
        or owned_pin(row)
        or (
            row["source_type"] == "own-game"
            and row["source_version"]
            in {
                VERSION,
                SHORT_VERSION,
                DEFENSE_VERSION,
                PROTECTION_VERSION,
                *CAPTURE_VERSIONS,
            }
        )
    ) and row["status"] == "needs_verification"
