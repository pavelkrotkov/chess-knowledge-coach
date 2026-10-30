"""Validate the whole supplied line and immediate defensive safety."""

import chess

from .fork_defense_safety import quiet_after, safe_material
from .fork_defense_scan import MAX_CANDIDATES, scan
from .pawn_scope import history_known
from .puzzle_session_validate import legal_move
from .related_fork_prevention_budget import take


def root(prompt, line):
    board = chess.Board(prompt)
    if not board.is_valid() or not history_known(board) or not 1 <= len(line) <= 64:
        return None
    replay = board.copy(stack=True)
    for text in line:
        replay.push(legal_move(replay, text))
    return board


def safe(board, move, budget):
    after = quiet_after(board, move)
    if after is None or not safe_material(after):
        return False
    if not take(budget, "proofs", MAX_CANDIDATES):
        return False
    result = scan(after)
    return bool(result is not None and not result["proven"] and not result["uncertain"])
