"""Bounded immediate-mate witnesses after one conditional opponent reply."""

from .mate_proof_moves import move_view
from .style_check_budget import record, reserve
from .style_check_evasions import MAX_MOVES
from .style_history_lines import history_safe


def witness(board, budget=None):
    if board.is_check():
        return {"status": "in_check", "moves": []}
    if not reserve(budget):
        return {"status": "report_budget_exhausted", "moves": []}
    result = _inspect(board)
    record(budget, result)
    return result


def _inspect(board):
    if not history_safe(board):
        return {"status": "history_unsupported", "moves": []}
    moves = list(board.legal_moves)
    if len(moves) > MAX_MOVES:
        return {"status": "budget_exceeded", "moves": []}
    if any(move.promotion for move in moves):
        return {"status": "promotion_unsupported", "moves": []}
    return {"status": "complete", "moves": _mates(board, moves)}


def _mates(board, moves):
    mates = []
    for move in sorted(moves, key=lambda item: item.uci()):
        if not board.gives_check(move):
            continue
        board.push(move)
        mate = board.is_checkmate()
        board.pop()
        if mate:
            mates.append(move_view(board, move))
    return mates
