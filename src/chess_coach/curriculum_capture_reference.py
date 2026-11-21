"""Resolve a current owner-bound capture review source."""

import json

import chess

from .objective_capture_contract import TARGET_VERSION
from .unified_source_current import snapshot_hash
from .unified_sources import resolve_source


def candidate(db, row, ref):
    try:
        if ref[0] != TARGET_VERSION:
            return None
        owner = json.loads(row["source_ref"])[0]
        source = resolve_source(db, "own-game", ref[0], ref[1], subject=owner)
        if snapshot_hash(source) != ref[2] or source["objective"] != "capture_named_target":
            return None
        board = chess.Board(source["prompt_fen"])
        return {
            "source_type": "own-game",
            "source_version": ref[0],
            "source_key": ref[1],
            "prompt_fen": source["prompt_fen"],
            "prompt_key": " ".join(board.fen(en_passant="fen").split()[:4]),
            "skill": "hanging_piece",
            "operation": "execute",
            "objective": "Capture the named target.",
            "unified_training": True,
        }
    except (TypeError, ValueError, KeyError, IndexError):
        return None
