"""Independently replay a relative-pin slide and an exposed bad move."""

from .pawn_scope import history_known
from .pin_defense_success import MAX_ROOT_MOVES
from .puzzle_session_validate import legal_move
from .related_pin_budget import take
from .related_pin_prevent_line import _replay
from .related_pin_slide_proof import pin, slide
from .related_pin_slide_witness import witness


def candidate_line(board, line, source, budget):
    try:
        if not line or not board.is_valid() or not history_known(board):
            return None
        good = legal_move(board, line[0])
        named = pin(board)
        if named is None or source["pin_kind"] != "relative_pin":
            return None
        return _candidate(board, good, named, line, budget)
    except (ValueError, TypeError, KeyError, IndexError):
        budget["unknown"] += 1
        return None


def _candidate(board, good, named, line, budget):
    if not slide(board, good, *named):
        return None
    moves = sorted(board.legal_moves, key=lambda move: move.uci())
    if len(moves) > MAX_ROOT_MOVES or not take(budget, "lines"):
        return None
    _replay(board, line)
    return witness(board, good, named, moves, budget)
