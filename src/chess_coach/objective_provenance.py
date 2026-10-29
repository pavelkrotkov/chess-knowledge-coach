"""Identify objective verifier and bounded result provenance."""

from .objective_capture_contract import GAIN_OBJECTIVE, TARGET_OBJECTIVE
from .objective_capture_judge import VERSION as CAPTURE_VERIFIER
from .objective_defense_judge import VERSION as DEFENSE_VERIFIER
from .objective_defense_source import OBJECTIVE as DEFENSE_OBJECTIVE
from .objective_protection_contract import OBJECTIVE as PROTECTION_OBJECTIVE
from .objective_protection_judge import VERSION as PROTECTION_VERIFIER
from .objective_short_source import OBJECTIVE as SHORT_OBJECTIVE

VERSION = "mate-one-verifier-v1"
SECONDS = 5.0
VERIFIERS = {
    PROTECTION_OBJECTIVE: PROTECTION_VERIFIER,
    TARGET_OBJECTIVE: CAPTURE_VERIFIER,
    GAIN_OBJECTIVE: CAPTURE_VERIFIER,
    DEFENSE_OBJECTIVE: DEFENSE_VERIFIER,
    SHORT_OBJECTIVE: "mate-two-verifier-v1",
}


def provenance(request, seconds=SECONDS):
    protection = request["objective_version"] == PROTECTION_OBJECTIVE
    capture = request["objective_version"] in {TARGET_OBJECTIVE, GAIN_OBJECTIVE}
    short = request["objective_version"] == SHORT_OBJECTIVE
    defense = request["objective_version"] == DEFENSE_OBJECTIVE
    verifier = VERIFIERS.get(request["objective_version"], VERSION)
    return {
        "verifier": verifier,
        "objective_version": request["objective_version"],
        "history_mode": request["history_mode"],
        "snapshot_hash": request["snapshot_hash"],
        "event_prefix_hash": request["event_prefix_hash"],
        "source_hash": request["source_hash"],
        "limits": {
            "plies": 3 if protection or short else 2 if capture or defense else 1,
            "compute_timeout_seconds": seconds,
        },
        "learning_eligible": False,
    }
