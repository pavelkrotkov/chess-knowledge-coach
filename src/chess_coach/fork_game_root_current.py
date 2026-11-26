"""Rebind retained fork roots to their exact original game histories."""

import chess

from .capture_game_root_current import _game
from .fork_game_counts import sample
from .fork_game_scope import bind_root, roots
from .related_fork_geometry import features


def _root(board, row):
    move, _, state = row
    parsed, squares = bind_root(board, row)
    expected = [chess.square_name(square) for square in squares]
    piece = board.piece_at(parsed.from_square)
    return {
        "move": move,
        "san": board.san(parsed),
        "targets": expected,
        "state": state,
        "features": features(board, parsed, piece, squares) if squares else None,
    }


def _turn(turn, context, board):
    if (context["mover"], context["played_move"]) != (turn["side"], turn["played"]):
        raise ValueError("fork turn changed")
    total = None if turn["total"] is None else len(roots(board))
    if total != turn["total"]:
        raise ValueError("fork root coverage changed")
    from .related_capture_position import _material, _phase

    return {
        **turn,
        "roots": [_root(board, root) for root in turn["roots"]],
        "material": _material(board),
        "phase": _phase(board),
        "time_control": context["time_control"],
    }


def project(db, learner, games, samples, *, check=None):
    for group, result in zip((games[:20], games[20:40]), samples, strict=True):
        by_game = [(item, _game(db, learner, item, check, turn=_turn)) for item in group]
        result["root_details"] = [turn for _, values in by_game for turn in values]
        result["root_game_coverage"] = [
            {"game_id": item["id"], "eligible": item["eligible"], "turns": values}
            for item, values in by_game
        ]


def samples(db, learner, games, check):
    newer, earlier = sample(games[:20]), sample(games[20:40])
    if check is not None:
        project(db, learner, games[:40], (newer, earlier), check=check)
    return newer, earlier
