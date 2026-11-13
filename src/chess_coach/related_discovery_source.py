"""Resolve an owned source and describe its proved discovered-mate shape."""

import chess

from .discovery_practice import VERSION as SOURCE_VERSION
from .discovery_practice_source import resolve
from .discovery_proof import prove
from .related_capture_position import _material, _phase
from .related_capture_source import _opening
from .unified_source_current import snapshot_hash


def source_for_evidence(db, subject, evidence_id):
    source = resolve(db, SOURCE_VERSION, str(evidence_id), subject)
    if source["objective"] != "checkmate":
        raise ValueError("discovered mate source unavailable")
    board = chess.Board(source["prompt_fen"])
    move = board.parse_uci(source["lines"][0].split()[0])
    features = shape(board, move)
    if features is None:
        raise ValueError("discovered mate source unavailable")
    source["provenance"]["source_fingerprint"] = snapshot_hash(source)
    source["features"] = features
    source["opening"] = _opening(db, source["provenance"]["position_id"])
    return source


def shape(board, move):
    if move not in board.legal_moves:
        return None
    after = board.copy(stack=True)
    after.push(move)
    if not after.is_checkmate():
        return None
    found = prove(board, move)
    if not found:
        return None
    slider = board.piece_at(chess.parse_square(found[0]["slider"]))
    mover = board.piece_at(move.from_square)
    if not slider or not mover:
        return None
    return {
        "geometry": (board.turn, mover.piece_type, slider.piece_type, found[0]["double_check"]),
        "phase": _phase(board),
        "material": _material(board),
    }
