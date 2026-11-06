"""Nominate a legal check response with a different defense structure."""

from itertools import islice

from .king_safety_scan import MAX_MOVES
from .style_defense_evasion import response
from .style_history_lines import lines_safe
from .style_schedule_clock import reached

FIELDS = ("king_move", "capture", "interposition", "countercheck")


def distinct(board, played):
    if not board.is_check():
        return False
    moves = list(islice(board.legal_moves, MAX_MOVES + 1))
    if len(moves) > MAX_MOVES or played not in moves or played.promotion:
        return None
    if len(moves) <= 1:
        return False
    return _compare(board, played, moves)


def _supported(board, move):
    return lines_safe(board, [{"pv": move.uci()}]) and not reached()


def _compare(board, played, moves):
    reference = response(board, played.uci())
    unknown = False
    for move in moves:
        if reached():
            return None
        if move == played:
            continue
        alternative = response(board, move.uci())
        if any(reference[key] != alternative[key] for key in FIELDS):
            if _supported(board, move):
                return True
            unknown = True
    return None if unknown else False
