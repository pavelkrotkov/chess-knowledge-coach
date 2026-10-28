"""Deterministic tactical motif detection."""

from typing import Any

import chess

from .motif_forks import _forks

DETECTOR_VERSION = "0.1.0"


def _hanging(board: chess.Board) -> list[dict[str, Any]]:
    facts = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is None or piece.piece_type == chess.KING:
            continue
        attackers = board.attackers(board.turn, square)
        defenders = board.attackers(piece.color, square)
        if attackers and piece.color != board.turn and not defenders:
            facts.append({"motif": "hanging_piece", "square": chess.square_name(square)})
    return facts


def _pins(board: chess.Board) -> list[dict[str, Any]]:
    facts = []
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None and piece.color != board.turn and board.is_pinned(piece.color, square):
            facts.append({"motif": "absolute_pin", "square": chess.square_name(square)})
    return facts


def detect_motifs(
    board: chess.Board, *, detector_version: str = DETECTOR_VERSION
) -> list[dict[str, Any]]:
    facts = _forks(board) + _hanging(board) + _pins(board)
    for fact in facts:
        fact["detector_version"] = detector_version
        fact["position_fen"] = board.fen()
    return facts
