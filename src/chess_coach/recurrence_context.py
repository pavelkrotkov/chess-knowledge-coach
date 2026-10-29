"""Describe recorded game and pre-move context without implying causation."""

import chess


def _clock(value):
    if value is None:
        return "unknown"
    return "30 seconds or less" if value <= 30 else "over 30 seconds"


def _rating(value):
    if value is None:
        return "unknown"
    base = value // 200 * 200
    return f"{base}-{base + 199}"


def _phase(fen):
    board = chess.Board(fen)
    pieces = sum(
        len(board.pieces(piece, color))
        for piece in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
        for color in chess.COLORS
    )
    return "high material" if pieces >= 12 else "medium material" if pieces >= 6 else "low material"


def context(decision):
    return {
        "side": decision["learner_color"],
        "time control": decision["time_control"] or "unknown",
        "clock": _clock(decision["clock_before_seconds"]),
        "rating": _rating(decision["mover_rating"]),
        "phase": _phase(decision["pre_move_fen"]),
        "opening familiarity": "unavailable",
    }
