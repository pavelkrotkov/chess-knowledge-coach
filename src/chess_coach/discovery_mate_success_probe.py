"""Nominate bounded positional discovered-check geometry without a game move."""

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
    found = []
    for move in sorted(moves, key=lambda item: item.uci()):
        check()
        if not probe.gives_check(move):
            continue
        found.extend(_geometry(probe, move))
        if len(found) > MAX_CANDIDATES:
            return None
    check()
    return found


def _geometry(board, move):
    return [
        {
            "move": move.uci(),
            "slider": chess.square_name(item["slider"]),
            "moved_from": chess.square_name(move.from_square),
            "moved_to": chess.square_name(move.to_square),
            "target": chess.square_name(item["target"]),
        }
        for item in discoveries(board, move)
        if board.piece_type_at(item["target"]) == chess.KING
    ]
