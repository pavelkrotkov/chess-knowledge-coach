"""Probe immediate legal attacks on non-pawn material without claiming a game line."""

from .material_threat_actions import collect


def threats(board, *, hypothetical):
    if not _valid_start(board):
        return None
    probe = board.copy(stack=False) if hypothetical else board.copy()
    if hypothetical:
        probe.turn = not probe.turn
    if not probe.is_valid() or probe.is_check():
        return None
    return collect(probe)


def _valid_start(board):
    return not (
        board.is_check()
        or board.ep_square is not None
        or board.is_repetition(2)
        or board.is_fifty_moves()
        or board.is_game_over()
    )
