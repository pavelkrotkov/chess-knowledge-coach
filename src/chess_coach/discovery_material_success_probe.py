"""Nominate bounded opposing moves that uncover a slider toward material."""

import chess

from .discovery_geometry import discoveries

MAX_MOVES = 128
MAX_CANDIDATES = 16


def candidates(board, check):
    probe = board.copy(stack=False)
    probe.turn = not probe.turn
    if not probe.is_valid() or probe.is_check():
        return None
    moves = list(probe.legal_moves)
    if len(moves) > MAX_MOVES:
        return None
    blockers = _blockers(probe)
    found = []
    for move in sorted(moves, key=lambda item: item.uci()):
        check()
        if not _eligible(probe, move, blockers):
            continue
        found.extend(_moves(probe, move))
        if len(found) > MAX_CANDIDATES:
            return None
    return found


# Only a friendly first blocker on a slider ray can expose that slider by
# moving. The full legal discovery check still validates each nomination.
def _blockers(board):
    result = set()
    for kind in (chess.BISHOP, chess.ROOK, chess.QUEEN):
        for slider in board.pieces(kind, board.turn):
            result.update(
                square for square in board.attacks(slider) if board.color_at(square) == board.turn
            )
    return result


def _moves(board, move):
    return [
        {"move": move.uci(), "slider": item["slider"], "target": item["target"]}
        for item in discoveries(board, move)
        if board.piece_type_at(item["target"]) != chess.KING
    ]


def _eligible(board, move, blockers):
    return move.from_square in blockers and not move.promotion and not board.is_castling(move)
