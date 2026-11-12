"""Compare the recorded continuation with a specifically verified defense."""

import time

import chess

from .discovery_material_check import origin, prevents
from .fork_defense_comparison import failed
from .material_ambiguity import ambiguous
from .objective_defense_judge import judge


def assess(board, actual, best, best_line, played_line, proof, started, check):
    lines, reason = failed(board, actual, best, played_line, best_line, proof)
    check()
    if not lines:
        return ambiguous("discovery_material_defense", reason)
    if any(len(lines[role]["uci"]) != 4 for role in ("played", "best")):
        return ambiguous("discovery_material_defense", "comparison_horizon_unsupported")
    if not prevents(board, actual, best, proof):
        return ambiguous("discovery_material_defense", "named_discovery_not_prevented")
    safe = judge(board.copy(), best, time.monotonic, started, 1.0, {})
    if safe["status"] != "correct":
        return ambiguous("discovery_material_defense", "immediate_mate_unresolved")
    check()
    return {
        "kind": "discovery_material_defense",
        "outcome": "failure",
        **lines,
        "threat": proof,
        "target_origin": chess.square_name(origin(actual, proof)),
        "defense": {"move": best.uci(), "san": board.san(best)},
        "boundary": "The recorded choice permits this tested discovered capture. The alternative prevents that named discovery and every immediate mate. Origin, other material threats and later consequences remain unknown.",
    }
