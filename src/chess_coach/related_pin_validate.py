"""Validate a complete candidate line while preserving its legal root history."""

from .pawn_scope import history_known
from .pin_proof_eligibility import eligible
from .puzzle_session_validate import legal_move


def root_and_move(board, line):
    if not board.is_valid() or not history_known(board) or not 3 <= len(line) <= 65:
        raise ValueError("pin candidate history unavailable")
    root = board.copy(stack=True)
    replay = board.copy(stack=True)
    for text in line:
        if replay.is_game_over(claim_draw=True):
            raise ValueError("pin candidate line ended")
        replay.push(legal_move(replay, text))
    move = legal_move(root, line[0])
    if not eligible(root, move):
        raise ValueError("pin creation outside supported scope")
    return root, move
