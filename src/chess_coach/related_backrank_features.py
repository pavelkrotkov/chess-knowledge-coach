"""Describe a supplied legal line ending in a genuine back-rank mate."""

import chess

from .back_rank_terminal import terminal
from .related_backrank_identity import replay
from .related_backrank_structure import describe
from .related_mate_features import mate_features


def features(prompt, line):
    result = mate_features(prompt, line)
    if result is None:
        return None
    try:
        attacker = chess.Board(prompt).turn
        board, tracked, promoted = replay(prompt, line)
        motif = terminal(board)
        if motif is None:
            return None
        result["backrank"] = describe(board, motif, attacker, tracked, promoted)
    except (ValueError, TypeError, AttributeError):
        return None
    return result
