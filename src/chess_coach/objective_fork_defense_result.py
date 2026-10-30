"""Build a bounded, non-learning fork-defense verification result."""

from .fork_defense_anchor import MAX_ANCHOR_MOVES
from .objective_fork_defense_budget import ANSWER_UNITS, LIMIT, SOURCE_UNITS
from .objective_fork_defense_contract import VERIFIER
from .objective_short_history import history_hash


def correct(board, move, seconds, base):
    return {
        **base,
        "status": "correct",
        "reason": "no_supported_immediate_fork_or_material_threat",
        "verifier": VERIFIER,
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
        "limits": {
            "worker_fork_proof_units": LIMIT,
            "source_observer_units_each": SOURCE_UNITS,
            "source_observer_checks_limit": 2,
            "source_anchor_moves_each": MAX_ANCHOR_MOVES,
            "answer_scan_units": ANSWER_UNITS,
            "compute_timeout_seconds": seconds,
        },
    }
