"""Describe a supplied legal line ending in a genuine back-rank mate."""

import chess

from .back_rank_terminal import terminal
from .related_mate_features import mate_features


def features(prompt, line):
    result = mate_features(prompt, line)
    if result is None:
        return None
    try:
        board = chess.Board(prompt)
        for text in line:
            board.push_uci(text)
        if terminal(board) is None:
            return None
    except (ValueError, TypeError, AttributeError):
        return None
    return result
