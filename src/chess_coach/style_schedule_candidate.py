"""Classify a fully replayed scheduling decision."""

import chess

from .style_defense_nomination import distinct
from .style_early_center import eligible as early_center
from .style_history_lines import history_safe


def candidate(position, board):
    move = chess.Move.from_uci(position["uci"])
    if not history_safe(board) or move.promotion:
        detail = "history_or_promotion_unsupported"
    elif board.legal_moves.count() <= 1:
        detail = "forced_move"
    else:
        detail = "eligible"
    structural = distinct(board, move) if detail == "eligible" and board.is_check() else None
    return {
        "structural_defense": structural,
        "early_center": detail == "eligible" and early_center(board, position["ply"]),
        "game_id": position["game_id"],
        "position_id": position["id"],
        "in_check": board.is_check(),
        "status": "ready" if detail == "eligible" else "unknown",
        "detail": detail,
    }
