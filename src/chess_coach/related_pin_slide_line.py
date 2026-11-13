"""Independently replay a relative-pin slide and an exposed bad move."""

from .pawn_scope import history_known
from .pin_defense_success import MAX_ROOT_MOVES
from .puzzle_session_validate import legal_move
from .related_pin_budget import slide_root, take
from .related_pin_prevent_line import _replay
from .related_pin_slide_proof import pin, slide_proof
from .related_pin_slide_witness import witness


def candidate_line(board, line, source, budget):
    try:
        if not line or not board.is_valid() or not history_known(board):
            return None
        good = legal_move(board, line[0])
        named = pin(board, source["pin_kind"])
        if named is None:
            return None
        return _candidate(board, good, named, line, budget)
    except (ValueError, TypeError, KeyError, IndexError):
        budget["unknown"] += 1
        return None


def _candidate(board, good, named, line, budget):
    attacker, pinned = named
    if not slide_root(budget, good, attacker, pinned):
        return None
    proof = slide_proof(board, good, *named)
    if proof is None:
        return None
    moves = sorted(board.legal_moves, key=lambda move: move.uci())
    if len(moves) > MAX_ROOT_MOVES or not take(budget, "lines"):
        return None
    _replay(board, line)
    return witness(board, good, named, moves, budget, proof)
