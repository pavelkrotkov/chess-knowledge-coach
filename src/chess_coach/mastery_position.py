"""Canonical chess positions used for independent-context comparisons."""

import chess


def position_key(board: chess.Board) -> str:
    if not board.is_valid():
        raise ValueError("invalid position")
    return " ".join(board.fen(en_passant="fen").split()[:4])
