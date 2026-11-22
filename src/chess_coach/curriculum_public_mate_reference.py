"""Recheck an owner-bound public mate review against its immutable source."""

import chess

from .public_mate_contract import BINDING, OBJECTIVE
from .public_training_source import resolve as public_source
from .unified_source_current import snapshot_hash


def candidate(db, ref):
    try:
        source = public_source(db, ref[0], ref[1], verify=False)
        if (
            source["objective"] != OBJECTIVE
            or source["provenance"].get("public_mate") != BINDING
            or snapshot_hash(source) != ref[2]
        ):
            return None
        board = chess.Board(source["prompt_fen"])
        return {
            "source_type": "public",
            "source_version": ref[0],
            "source_key": ref[1],
            "prompt_fen": source["prompt_fen"],
            "prompt_key": " ".join(board.fen(en_passant="fen").split()[:4]),
            "skill": "mate_in_one",
            "operation": "execute",
            "objective": "Find checkmate in one move.",
            "unified_training": True,
        }
    except (TypeError, ValueError, KeyError, IndexError):
        return None
