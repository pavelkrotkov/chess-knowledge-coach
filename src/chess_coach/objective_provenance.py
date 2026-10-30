"""Identify objective verifier and bounded result provenance."""

from .objective_capture_contract import GAIN_OBJECTIVE, TARGET_OBJECTIVE
from .objective_capture_judge import VERSION as CAPTURE_VERIFIER
from .objective_defense_judge import VERSION as DEFENSE_VERIFIER
from .objective_defense_source import OBJECTIVE as DEFENSE_OBJECTIVE
from .objective_fork_contract import OBJECTIVE as FORK_OBJECTIVE
from .objective_fork_contract import VERIFIER as FORK_VERIFIER
from .objective_fork_defense_contract import OBJECTIVE as FORK_DEFENSE_OBJECTIVE
from .objective_fork_defense_contract import VERIFIER as FORK_DEFENSE_VERIFIER
from .objective_pawn_contract import OBJECTIVE as PAWN_OBJECTIVE
from .objective_pawn_contract import VERIFIER as PAWN_VERIFIER
from .objective_pin_contract import OBJECTIVE as PIN_OBJECTIVE
from .objective_pin_contract import VERIFIER as PIN_VERIFIER
from .objective_pin_prevent_contract import OBJECTIVE as PIN_PREVENT_OBJECTIVE
from .objective_pin_prevent_contract import VERIFIER as PIN_PREVENT_VERIFIER
from .objective_promotion_contract import VERIFIER as PROMOTION_VERIFIER
from .objective_promotion_contract import VERSION as PROMOTION_VERSION
from .objective_protection_contract import OBJECTIVE as PROTECTION_OBJECTIVE
from .objective_protection_judge import VERSION as PROTECTION_VERIFIER
from .objective_short_source import OBJECTIVE as SHORT_OBJECTIVE
from .pawn_proof import MAX_PLIES as PAWN_MAX_PLIES

VERSION = "mate-one-verifier-v1"
SECONDS = 5.0
VERIFIERS = {
    FORK_OBJECTIVE: FORK_VERIFIER,
    FORK_DEFENSE_OBJECTIVE: FORK_DEFENSE_VERIFIER,
    PIN_OBJECTIVE: PIN_VERIFIER,
    PIN_PREVENT_OBJECTIVE: PIN_PREVENT_VERIFIER,
    PROMOTION_VERSION: PROMOTION_VERIFIER,
    PAWN_OBJECTIVE: PAWN_VERIFIER,
    PROTECTION_OBJECTIVE: PROTECTION_VERIFIER,
    TARGET_OBJECTIVE: CAPTURE_VERIFIER,
    GAIN_OBJECTIVE: CAPTURE_VERIFIER,
    DEFENSE_OBJECTIVE: DEFENSE_VERIFIER,
    SHORT_OBJECTIVE: "mate-two-verifier-v1",
}

PLIES = {
    FORK_OBJECTIVE: 3,
    FORK_DEFENSE_OBJECTIVE: 3,
    PIN_OBJECTIVE: 3,
    PIN_PREVENT_OBJECTIVE: 3,
    PROMOTION_VERSION: 3,
    PAWN_OBJECTIVE: PAWN_MAX_PLIES,
    PROTECTION_OBJECTIVE: 3,
    SHORT_OBJECTIVE: 3,
    TARGET_OBJECTIVE: 2,
    GAIN_OBJECTIVE: 2,
    DEFENSE_OBJECTIVE: 2,
}


def provenance(request, seconds=SECONDS):
    verifier = VERIFIERS.get(request["objective_version"], VERSION)
    return {
        "verifier": verifier,
        "objective_version": request["objective_version"],
        "history_mode": request["history_mode"],
        "snapshot_hash": request["snapshot_hash"],
        "event_prefix_hash": request["event_prefix_hash"],
        "source_hash": request["source_hash"],
        "limits": {
            "plies": PLIES.get(request["objective_version"], 1),
            "compute_timeout_seconds": seconds,
        },
        "learning_eligible": False,
    }
