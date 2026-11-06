"""Nominate learner pre-move keys from consecutive stored plies."""

from itertools import pairwise

import chess

from .opening_storage import position_key

MIN_PLY = 4


def game_positions(game, color, positions):
    items = []
    seen = set()
    for previous, current in pairwise(positions):
        key = _key(previous, current, color)
        if key is None or key in seen:
            continue
        seen.add(key)
        items.append(
            (
                key,
                {
                    "game_id": game["id"],
                    "position_id": current["id"],
                    "played_at": game["projected_start"],
                },
            )
        )
    return items


def _key(previous, current, color):
    if current["ply"] < MIN_PLY or current["ply"] != previous["ply"] + 1:
        return None
    return _board_key(previous["fen"], color)


def _board_key(fen, color):
    if not isinstance(fen, str) or len(fen) > 200:
        return None
    try:
        board = chess.Board(fen)
        if not board.is_valid() or ("white" if board.turn else "black") != color:
            return None
        return color, position_key(board)
    except (ValueError, TypeError):
        return None
