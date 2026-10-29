"""Identify objective verifier and bounded result provenance."""

from .objective_defense_judge import VERSION as DEFENSE_VERIFIER
from .objective_defense_source import OBJECTIVE as DEFENSE_OBJECTIVE
from .objective_short_source import OBJECTIVE as SHORT_OBJECTIVE

VERSION = "mate-one-verifier-v1"
SECONDS = 5.0


def provenance(request, seconds=SECONDS):
    short = request["objective_version"] == SHORT_OBJECTIVE
    defense = request["objective_version"] == DEFENSE_OBJECTIVE
    verifier = DEFENSE_VERIFIER if defense else "mate-two-verifier-v1" if short else VERSION
    return {
        "verifier": verifier,
        "objective_version": request["objective_version"],
        "history_mode": request["history_mode"],
        "snapshot_hash": request["snapshot_hash"],
        "event_prefix_hash": request["event_prefix_hash"],
        "source_hash": request["source_hash"],
        "limits": {
            "plies": 2 if defense else 3 if short else 1,
            "compute_timeout_seconds": seconds,
        },
        "learning_eligible": False,
    }
