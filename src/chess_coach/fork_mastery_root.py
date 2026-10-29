"""Restrict fork roots to the independently qualified move shapes."""

import chess


def supported_root(fen, payload):
    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(payload["proof"]["move"])
        piece = board.piece_at(move.from_square)
        return (
            move in board.legal_moves
            and not board.is_capture(move)
            and not move.promotion
            and piece is not None
            and piece.piece_type in {chess.PAWN, chess.KNIGHT}
        )
    except (ValueError, TypeError, KeyError):
        return False
