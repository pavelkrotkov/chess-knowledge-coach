"""Classify a verified mover-perspective pawn interval."""

from . import pawn_proof, pawn_tables
from .objective_capture_proof import unknown
from .objective_pawn_bounds import alternative, root_goal, verdict
from .objective_pawn_contract import VERIFIER as VERSION
from .objective_pawn_reply import reply
from .objective_short_history import history_hash


def classify(board, move, goal, proof, clock, start, seconds, base):
    root = root_goal(proof)
    if root is None or root < goal:
        return unknown(base, "root_result_unresolved")
    bounds = alternative(proof, move.uci())
    if bounds is None:
        return unknown(base, "alternative_result_unresolved")
    status, reason = verdict(*bounds, goal)
    nodes = proof.get("nodes")
    continuation = {"status": "unavailable", "reason": "result_not_proved"}
    if status == "correct" and type(nodes) is int and 0 <= nodes <= pawn_proof.MAX_NODES // 2:
        continuation = reply(board, move, goal, nodes, clock, start, seconds)
    return {
        **base,
        "status": status,
        "reason": reason,
        "verifier": VERSION,
        "continuation": continuation,
        "history_hash": history_hash(board),
        "move": move.uci(),
        "san": board.san(move),
        "goal": goal,
        "lower": bounds[0],
        "upper": bounds[1],
        "proof_version": pawn_proof.VERSION,
        "proof_manifest_sha256": pawn_tables.MANIFEST_SHA256,
        "limits": {
            "node_limit": pawn_proof.MAX_NODES,
            "max_plies": pawn_proof.MAX_PLIES,
            "compute_timeout_seconds": seconds,
        },
    }
