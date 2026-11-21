"""Resolve a current owner-bound fork review source."""

import json

import chess

from .objective_fork_contract import GOAL, MISS_VERSION
from .unified_source_current import snapshot_hash
from .unified_sources import resolve_source


def candidate(db, row, ref):
    try:
        if ref[0] != MISS_VERSION:
            return None
        owner = json.loads(row["source_ref"])[0]
        source = resolve_source(db, "own-game", ref[0], ref[1], subject=owner)
        if snapshot_hash(source) != ref[2] or source["objective"] != GOAL:
            return None
        board = chess.Board(source["prompt_fen"])
        return {
            "source_type": "own-game",
            "source_version": ref[0],
            "source_key": ref[1],
            "prompt_fen": source["prompt_fen"],
            "prompt_key": " ".join(board.fen(en_passant="fen").split()[:4]),
            "skill": "fork",
            "operation": "execute",
            "objective": "Execute the named fork.",
            "unified_training": True,
        }
    except (TypeError, ValueError, KeyError, IndexError):
        return None
