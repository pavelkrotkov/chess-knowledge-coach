"""Verify a supplied defense against an independently proved counterfactual pin."""

from .objective_pin_prevent_created import _prepare
from .pawn_scope import history_known
from .puzzle_session_validate import legal_move
from .related_pin_created_geometry import geometry
from .related_pin_created_search import search
from .related_pin_prevent_line import _replay


def candidate_line(board, line, source, budget):
    try:
        if not line or not board.is_valid() or not history_known(board):
            return None
        good = legal_move(board, line[0])
        after, reason = _prepare(board, good)
        if reason or geometry(after) != []:
            return None
        _replay(board, line)
        return search(board, good, source, budget)
    except (ValueError, TypeError, KeyError, IndexError):
        budget["unknown"] += 1
        return None
