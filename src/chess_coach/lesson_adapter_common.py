"""Validate the legal lines used by lesson adapters."""

import chess

from .lesson_lines import legal_san


def valid_square(value):
    return isinstance(value, str) and value in chess.SQUARE_NAMES


def line(fen, label, moves):
    result = legal_san(fen, moves)
    return {"label": label, "moves": result} if result else None
