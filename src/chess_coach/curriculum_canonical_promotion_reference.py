"""Rebind an owner-bound immediate-promotion review without solving on GET."""

import chess

from .objective_promotion_contract import NOW
from .plan_promotion_catalog import VERSION, collection
from .public_training_source import resolve as public_source
from .unified_source_current import snapshot_hash


def candidate(db, ref):
    try:
        if ref[0] != VERSION:
            return None
        collection(db)
        source = public_source(db, ref[0], ref[1], verify=False)
        if source["objective"] != NOW or snapshot_hash(source) != ref[2]:
            return None
        board = chess.Board(source["prompt_fen"])
        return {
            "source_type": "public",
            "source_version": ref[0],
            "source_key": ref[1],
            "prompt_fen": source["prompt_fen"],
            "prompt_key": " ".join(board.fen(en_passant="fen").split()[:4]),
            "skill": "promotion",
            "operation": "execute",
            "objective": "Promote a pawn now.",
            "unified_training": True,
        }
    except (TypeError, ValueError, KeyError, IndexError):
        return None
