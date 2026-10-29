"""Prove a legal target capture by immediate mate or bounded material gain."""

import chess

from .fork_capture import capture as material_capture
from .material_exchange_rules import unclear


def capture(board, attacker, target, color, initial):
    if unclear(board):
        return None
    move = chess.Move(attacker, target)
    if move in board.legal_moves and board.is_capture(move):
        after = board.copy()
        after.push(move)
        if after.is_checkmate():
            return move.uci()
    return material_capture(board, attacker, target, color, initial)
