"""Build a bounded, non-learning fork-defense verification result."""

from .fork_defense_anchor import MAX_ANCHOR_MOVES
from .fork_defense_probe import MAX_MOVES as MAX_HYPOTHETICAL_MOVES
from .objective_fork_avoidance_contract import OBJECTIVE as AVOIDANCE_OBJECTIVE
from .objective_fork_defense_budget import ANSWER_UNITS, LIMIT, SOURCE_UNITS
from .objective_short_history import history_hash


def correct(board, move, seconds, base):
    return {
        **base,
        "status": "correct",
        "reason": "no_supported_immediate_fork_or_material_threat",
        "verifier": base["verifier"],
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
        "limits": _limits(base, seconds),
    }


def _limits(base, seconds):
    result = {
        "worker_fork_proof_units": LIMIT,
        "source_observer_units_each": SOURCE_UNITS,
        "source_observer_checks_limit": 2,
        "answer_scan_units": ANSWER_UNITS,
        "compute_timeout_seconds": seconds,
    }
    if base["objective_version"] == AVOIDANCE_OBJECTIVE:
        result["hypothetical_checks_per_source_refresh"] = 2
        result["worker_hypothetical_checks_limit"] = 4
        result["hypothetical_legal_list_admission_limit"] = MAX_HYPOTHETICAL_MOVES
    else:
        result["source_anchor_moves_each"] = MAX_ANCHOR_MOVES
    return result
