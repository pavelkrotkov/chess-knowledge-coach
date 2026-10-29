"""Describe legal rook file choices and bounded immediate captures."""

import chess

from .material_exchange_rules import unclear
from .material_lines import continuation
from .rook_plan_geometry import file_kind
from .rook_plan_observation import VERSION as VERSION
from .rook_plan_observation import observation
from .structure_features import extract_features


def _rook_file(board, move, features, color):
    if board.piece_type_at(move.from_square) != chess.ROOK:
        return None
    return file_kind(features, color, move.to_square)


def lesson(board, played, best, played_line):
    """Compare two distinct, legally replayed recorded roots; no skill outcome is inferred."""
    if unclear(board):
        return None
    lines = {"best": continuation(board, best), "played": continuation(board, played_line, played)}
    if any(value is None for value in lines.values()):
        return None
    best_line, actual = lines["best"], lines["played"]
    if best_line["uci"][0] == actual["uci"][0]:
        return None
    features = extract_features(board)
    for line in (best_line, actual):
        move = board.parse_uci(line["uci"][0])
        color = "white" if board.turn else "black"
        kind = _rook_file(board, move, features, color)
        if not kind:
            continue
        return observation(board, move, features, color, kind, lines)
    return None
