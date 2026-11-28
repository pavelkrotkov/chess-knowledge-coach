"""Build a complete bounded short-mate root certificate and source example."""

import time

from .fact_fingerprint import canonical, digest
from .mate_proof import MAX_NODES, _root
from .objective_short_history import history_hash
from .objective_short_judge import DeadlineBudget
from .opening_public_proof_replay import _attribution


def proof(board, deadline):
    budget = DeadlineBudget(MAX_NODES, time.monotonic, deadline)
    roots = [
        _root(board, move, budget)
        for move in sorted(board.legal_moves, key=lambda move: move.uci())
    ]
    return {
        "alternatives": roots,
        "nodes": budget.nodes,
        "incomplete": any(root["status"] == "unknown" for root in roots),
        "supported": any(
            root["status"] == "proved" and root["distance_plies"] == 3 for root in roots
        ),
    }


def example(db, row, binding, source, moves, rows, ply, board, recorded, result):
    value = {
        "ply": ply,
        "fen": board.fen(),
        "side_to_move": "white" if board.turn else "black",
        "recorded_uci": recorded.uci(),
        "recorded_san": board.san(recorded),
        "alternatives": result["alternatives"],
        "nodes": result["nodes"],
        "history_hash": history_hash(board),
        "source_identity": source,
        "history_sha256": digest(canonical(rows[: ply - 1])),
        "full_history_sha256": digest(canonical(moves)),
    }
    _attribution(db, row[0], row[2], binding, value)
    return value
