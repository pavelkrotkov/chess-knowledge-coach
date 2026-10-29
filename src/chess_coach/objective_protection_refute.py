"""Require a concrete bounded profitable capture as a refutation."""

import chess

from .material_capture_gain import capture_gain
from .material_reply_guard import unresolved_reply


def witness(board, texts):
    for text in sorted(texts):
        move = chess.Move.from_uci(text)
        if _proven(board, move):
            return text
    return None


def _proven(board, move):
    if move not in board.legal_moves or board.gives_check(move):
        return False
    gain, reason, _ = capture_gain(board, move, board.piece_at(move.to_square))
    return reason is None and gain >= 3 and not unresolved_reply(board, move)
