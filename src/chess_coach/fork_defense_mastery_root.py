"""Restrict verified prevention observations to knight fork threats."""

import chess

from .fork_defense_safety import quiet_after


def supported_threat(fen, payload):
    try:
        board = chess.Board(fen)
        actual = board.parse_uci(payload["played"]["uci"][0])
        if actual not in board.legal_moves or quiet_after(board, actual) is None:
            return False
        after, proof = _branch(board, payload, actual)
        return after is not None and _knight_root(after, proof)
    except (ValueError, TypeError, KeyError, IndexError):
        return False


def _branch(board, payload, actual):
    if payload["outcome"] == "success":
        anchor = payload["threats"][0]
        alternative = board.parse_uci(anchor["move"])
        if alternative not in board.legal_moves:
            return None, None
        return quiet_after(board, alternative), anchor["fork"]
    return quiet_after(board, actual), payload["fork"]


def _knight_root(board, proof):
    move = board.parse_uci(proof["move"])
    piece = board.piece_at(move.from_square)
    return (
        move in board.legal_moves
        and not board.is_capture(move)
        and not move.promotion
        and piece is not None
        and piece.piece_type == chess.KNIGHT
    )
