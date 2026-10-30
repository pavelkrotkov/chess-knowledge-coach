"""Recognize a supported specified-piece defense in a complete legal line."""

import time

import chess

from .objective_protection_before import probe
from .objective_protection_judge import judge
from .pawn_scope import history_known
from .puzzle_session_validate import legal_move
from .related_capture_position import _features, compatible
from .related_protection_mechanism import mechanism


def protection_features(prompt, line):
    try:
        board = chess.Board(prompt)
        if not board.is_valid() or not history_known(board) or not 1 <= len(line) <= 64:
            return None
        replay = board.copy(stack=True)
        for text in line:
            replay.push(legal_move(replay, text))
        move = legal_move(board, line[0])
        threat = probe(board)
        if threat is None:
            return None
        target = next(iter(threat["targets"]))
        result = judge(board, move, target, time.monotonic, time.monotonic(), 5.0, {})
        if result["status"] != "correct":
            return None
        features = _features(board, move, board.piece_at(move.from_square), board.piece_at(target))
        features["target_square"] = chess.square_name(target)
        features["mechanism"] = mechanism(board, move, target, threat)
        return features
    except (ValueError, TypeError, IndexError, KeyError):
        return None


def same_mechanism(source, candidate):
    """Match piece roles and defensive action after the candidate proof."""
    return compatible(source, candidate) and source["mechanism"] == candidate["mechanism"]
