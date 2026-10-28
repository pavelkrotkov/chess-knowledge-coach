"""Deterministic, narrow mate-in-one decision facts."""

from __future__ import annotations

import chess


def mate_in_one_fact(fen: str, played_move: str) -> dict[str, object] | None:
    """Describe a legal mating opportunity, without inferring player cognition."""
    try:
        board = chess.Board(fen)
        move = board.parse_uci(played_move)
        if not board.is_valid() or not move or not board.is_legal(move):
            raise ValueError("invalid decision")
        mates = _mating_moves(board)
        if not mates:
            return None
        board.push(move)
        return {
            "pre_move_fen": fen,
            "played_move": move.uci(),
            "mating_moves": mates,
            "played_checkmate": board.is_checkmate(),
            "played_stalemate": board.is_stalemate(),
        }
    except (ValueError, TypeError):
        raise ValueError("invalid tactical decision") from None


def _mating_moves(board: chess.Board) -> list[str]:
    mates = []
    for move in list(board.legal_moves):
        board.push(move)
        if board.is_checkmate():
            mates.append(move.uci())
        board.pop()
    return sorted(mates)
