"""Rebind retained capture roots to their original pre-move game sources."""

import chess

from .capture_game_proof import _detail, _target
from .capture_game_root_validate import valid
from .related_capture_position import _features, _material, _phase
from .short_mate_game_source import prepare
from .short_mate_trend_cohort import fingerprint


# Legal replay rebinds geometry; it never re-proves the retained root state.
def _root(board, root):
    move = board.parse_uci(root[0])
    if (
        root[2] not in {"proved", "outside", "unknown"}
        or not board.is_capture(move)
        or _detail(board, move, root[2]) != root
    ):
        raise ValueError("root source changed")
    square, target = _target(board, move)
    mover = board.piece_at(move.from_square)
    return {
        "move": root[0],
        "san": board.san(move),
        "mover": chess.piece_name(mover.piece_type),
        "target": chess.piece_name(target.piece_type),
        "target_square": chess.square_name(square),
        "state": root[2],
        "mechanism": root[3],
        "features": _features(board, move, mover, target),
    }


def _turn(turn, context, board):
    if (context["mover"], context["played_move"]) != (turn["side"], turn["played"]):
        raise ValueError("turn source changed")
    total = (
        None if turn["total"] is None else sum(board.is_capture(move) for move in board.legal_moves)
    )
    if turn["total"] != total:
        raise ValueError("root coverage changed")
    return {
        **turn,
        "roots": [_root(board, root) for root in turn["roots"]],
        "material": _material(board),
        "phase": _phase(board),
        "time_control": context["time_control"],
    }


def _game(db, learner, item, check):
    turns = (item.get("root_details") or {}).get("turns", ())
    if not turns:
        return []
    source = prepare(db, learner, item["id"], check=check)
    if (source["identity"], fingerprint(source["signature"])) != (
        item["identity"],
        item["signature"],
    ):
        raise ValueError("game source changed")
    pairs = {
        context["position_id"]: (context, board)
        for context, board in source["pairs"]
        if context["subject"]
    }
    return [
        {**_turn(turn, *pairs[turn["position_id"]]), "game_id": item["id"], "date": item["date"]}
        for turn in turns
    ]


def project(db, learner, games, samples, *, check=None):
    if not valid(games):
        raise ValueError("root coverage unavailable")
    for group, sample in zip((games[:20], games[20:40]), samples, strict=True):
        by_game = [(item, _game(db, learner, item, check)) for item in group]
        turns = [turn for _, values in by_game for turn in values]
        sample.update(
            root_details=turns,
            root_unattributed=sample["eligible"] - sample["unchecked"] - len(turns),
            root_game_coverage=[
                {"game_id": item["id"], "eligible": item["eligible"], "turns": values}
                for item, values in by_game
            ],
        )
