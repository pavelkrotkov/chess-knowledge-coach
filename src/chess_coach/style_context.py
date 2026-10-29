"""Decision context, observed prior positions and pre-move structural labels."""

import chess

from .named_structures import VERSION as STRUCTURE_VERSION
from .named_structures import match_structures
from .style_opening import opening_context


def _band(value):
    if value is None:
        return "unknown"
    base = value // 200 * 200
    return f"{base}-{base + 199}"


def _phase(board):
    total = sum(
        len(board.pieces(piece, side))
        for piece in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
        for side in chess.COLORS
    )
    return "high material" if total >= 12 else "medium material" if total >= 6 else "low material"


def describe_context(db, context, opening):
    board = chess.Board(context["pre_move_fen"])
    clock = context["clock_before_seconds"]
    return {
        "color": context["learner_color"],
        "rating": _band(context["mover_rating"]),
        "opponent_rating": _band(context["other_rating"]),
        "time_control": context["time_control"] or "unknown",
        "clock_before_seconds": clock,
        "clock_band": "unknown"
        if clock is None
        else "30 seconds or less"
        if clock <= 30
        else "over 30 seconds",
        "phase": _phase(board),
        "familiarity": context["familiarity"],
        "prior_observed_games": context["prior_observed_games"],
        "observed_at": context["observation_at"],
        "opening": opening_context(db, opening, board),
        "structures": sorted({item["family"] for item in match_structures(board)}),
        "structure_matcher": STRUCTURE_VERSION,
    }
