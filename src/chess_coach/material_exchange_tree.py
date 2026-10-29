"""Explore legal target-square recaptures under an explicit node and ply cap."""

from .material_exchange_rules import MAX_EXCHANGE_PLIES, captures, ordinary_capture, over_limit
from .material_values import VALUES


def recaptures(board, square, beneficiary, gain, budget, depth):
    budget[0] += 1
    if over_limit(board, budget, depth):
        return None
    options = captures(board, square)
    if not options:
        return gain
    if depth == MAX_EXCHANGE_PLIES:
        return None
    return _evaluate(board, square, beneficiary, gain, budget, depth, options)


def _evaluate(board, square, beneficiary, gain, budget, depth, options):
    values = [gain]
    for move in options:
        value = _child_value(board, move, square, beneficiary, gain, budget, depth)
        if value is None:
            return None
        values.append(value)
    return max(values) if board.turn == beneficiary else min(values)


def _child_value(board, move, square, beneficiary, gain, budget, depth):
    target = board.piece_at(square)
    if not ordinary_capture(board, move) or target is None or target.piece_type not in VALUES:
        return None
    delta = VALUES[target.piece_type] * (1 if board.turn == beneficiary else -1)
    child = board.copy()
    child.push(move)
    return recaptures(child, square, beneficiary, gain + delta, budget, depth + 1)
