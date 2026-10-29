"""Replay qualified continuations and identify target-square captures."""

import chess

from .material_exchange import exchange
from .material_lines import continuation
from .pawn_structure_immediate import immediate


def _capture(board, move, target, ply):
    square = chess.parse_square(target["square"])
    piece = board.piece_at(square)
    if move.to_square != square or not piece or piece.piece_type != chess.PAWN:
        return None
    if piece.color != (target["color"] == "white"):
        return None
    gain = exchange(board, move)
    return {**target, "ply": ply, "exchange_gain": gain} if gain is not None and gain > 0 else None


def line(board, source, root, targets):
    verified = continuation(board, source, root)
    if verified is None:
        return None
    moves = verified["uci"]
    replay, active, captures = board.copy(), list(targets), []
    for ply, text in enumerate(moves, 1):
        move = replay.parse_uci(text)
        captures.extend(item for target in active if (item := _capture(replay, move, target, ply)))
        active = [
            target
            for target in active
            if chess.parse_square(target["square"]) not in (move.from_square, move.to_square)
        ]
        replay.push(move)
    return {**verified, "captures": captures, "immediate": immediate(board, moves[0], targets)}
