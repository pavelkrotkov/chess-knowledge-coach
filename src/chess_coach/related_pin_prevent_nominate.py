"""Find a cheap same-kind existing pin capture before proof."""

from .pawn_scope import history_known
from .pin_existing import existing
from .puzzle_session_validate import legal_move


def nominate(board, line, source):
    if not line or not board.is_valid() or not history_known(board):
        return None
    move = legal_move(board, line[0])
    if not board.is_capture(move):
        return None
    candidates = existing(board)
    if len(candidates) != 1:
        return None
    attacker, pin = candidates[0]
    if pin["type"] != source["pin_kind"] or move.to_square != attacker:
        return None
    return move, attacker, pin
