"""Rebind retained capture roots to their original pre-move game sources."""

import chess

from .capture_game_proof import _detail, _target
from .related_capture_position import _features, _material, _phase
from .short_mate_game_source import prepare
from .short_mate_trend_cohort import fingerprint


def _root(board, root):
    move = chess.Move.from_uci(root[0])
    if root[2] not in {"proved", "outside", "unknown"}:
        raise ValueError("root state unavailable")
    if (
        move not in board.legal_moves
        or not board.is_capture(move)
        or _detail(board, move, root[2]) != root
    ):
        raise ValueError("root source changed")
    square, target = _target(board, move)
    mover = board.piece_at(move.from_square)
    feature = _features(board, move, mover, target) if target else None
    return {
        "move": root[0],
        "san": board.san(move),
        "target": chess.piece_name(target.piece_type) if target else None,
        "target_square": chess.square_name(square),
        "state": root[2],
        "mechanism": root[3],
        "features": feature,
    }


def _turn(turn, context, board):
    if (context["mover"], context["played_move"]) != (turn["side"], turn["played"]):
        raise ValueError("turn source changed")
    roots = turn["roots"]
    if len(roots) > 32 or len({root[0] for root in roots}) != len(roots):
        raise ValueError("root coverage unavailable")
    attempted = turn["attempted"]
    if turn["total"] is None:
        if roots or attempted != 0 or turn["unsearched"] is not None:
            raise ValueError("root coverage unavailable")
    else:
        total = sum(board.is_capture(move) for move in board.legal_moves)
        if type(attempted) is not int or not len(roots) <= attempted <= total:
            raise ValueError("root coverage unavailable")
        if (turn["total"], turn["unsearched"]) != (total, total - attempted):
            raise ValueError("root coverage changed")
    return {
        **turn,
        "roots": [_root(board, root) for root in roots],
        "material": _material(board),
        "phase": _phase(board),
        "time_control": context["time_control"],
    }


def _game(db, learner, item):
    turns = (item.get("root_details") or {}).get("turns", ())
    if not turns:
        return []
    source = prepare(db, learner, item["id"])
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


def project(db, learner, games):
    turns = [turn for item in games for turn in _game(db, learner, item)]
    return {turn["position_id"]: turn for turn in turns}
