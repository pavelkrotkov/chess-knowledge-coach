"""Reject invalid or history-uncertain standalone promotion inputs."""

from .objective_promotion_contract import OBJECTIVES
from .pawn_scope import history_known


def reason(board, move, objective, clock, start, seconds):
    if clock() - start > seconds:
        return "timeout"
    if objective not in OBJECTIVES:
        return "unsupported_objective"
    if not _history_available(board):
        return "history_or_draw_unavailable"
    if board.is_game_over(claim_draw=False) or not move or move not in board.legal_moves:
        return "terminal_or_illegal_move"
    return None


def _history_available(board):
    return board.is_valid() and history_known(board) and not board.can_claim_draw()
