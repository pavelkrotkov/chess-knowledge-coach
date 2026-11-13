"""Check every defense and the named immediate material capture."""

import chess

from .material_exchange import exchange
from .material_lines import material
from .material_reply_guard import MAX_REPLIES, MIN_GAIN
from .objective_protection_other import reason as counterplay_reason


def _capture(after, reply, slider, target, piece, color, initial):
    board = after.copy()
    reply_san = board.san(reply)
    board.push(reply)
    if board.is_game_over(claim_draw=True) or board.piece_at(target) != piece:
        return None
    capture = chess.Move(slider, target)
    if capture not in board.legal_moves:
        return None
    gain = exchange(board, capture)
    if gain is None or material(board, color) - initial + gain < MIN_GAIN:
        return None
    capture_san = board.san(capture)
    board.push(capture)
    # A different capture or check can offset the named exchange; leave it unknown.
    if counterplay_reason(board, list(board.legal_moves), target):
        return None
    return reply_san, capture_san


def witness(board, move, after, target, piece, deadline, clock):
    if after.is_game_over(claim_draw=True):
        return None
    replies = sorted(after.legal_moves, key=lambda reply: reply.uci())
    if not 0 < len(replies) <= MAX_REPLIES:
        return None
    initial, line = material(board, board.turn), None
    for reply in replies:
        if clock() >= deadline:
            return None
        result = _capture(after, reply, move.to_square, target, piece, board.turn, initial)
        if result is None or clock() >= deadline:
            return None
        line = line or result
    return line, len(replies)
