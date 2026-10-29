"""Identify positional fork candidates without inventing game history."""

from .fork_geometry import _valuable

MAX_MOVES = 128
MAX_CANDIDATES = 16


def hypothetical(board):
    if _unsupported(board):
        return None
    probe = board.copy(stack=False)
    probe.turn = not probe.turn
    if not probe.is_valid() or probe.is_check():
        return None
    moves = list(probe.legal_moves)
    if len(moves) > MAX_MOVES:
        return None
    result = {}
    for move in moves:
        squares = _targets(probe, move)
        if len(squares) >= 2:
            result[move.uci()] = squares
    return result if len(result) <= MAX_CANDIDATES else None


def _targets(board, move):
    if board.is_capture(move) or move.promotion:
        return []
    after = board.copy(stack=False)
    after.push(move)
    return sorted(
        square
        for square in after.attacks(move.to_square)
        if _valuable(after.piece_at(square), board.turn)
    )


def _unsupported(board):
    return (
        board.is_check()
        or board.ep_square is not None
        or board.is_repetition(2)
        or board.is_fifty_moves()
        or board.is_game_over()
    )
