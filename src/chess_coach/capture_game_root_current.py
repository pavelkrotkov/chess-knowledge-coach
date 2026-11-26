"""Rebind cached capture-root details to their exact pre-move game source."""

import chess

from .capture_game_proof import _detail
from .capture_game_root_budget import _items
from .related_capture_position import _material, _phase
from .short_mate_game_source import prepare
from .short_mate_trend_cohort import fingerprint


def _coverage(turn, board):
    roots = turn["roots"]
    if turn["total"] is None:
        return not roots and turn["unsearched"] is None
    total = sum(board.is_capture(move) for move in board.legal_moves)
    return (turn["total"], turn["unsearched"]) == (total, total - len(roots))


def _turn_matches(turn, context, board):
    if (context["mover"], context["played_move"]) != (turn["side"], turn["played"]):
        return False
    if list(_material(board)) != turn["material"] or _phase(board) != turn["phase"]:
        return False
    roots = turn["roots"]
    if len(roots) > 32 or not _coverage(turn, board):
        return False
    if len({root[0] for root in roots}) != len(roots):
        return False
    for root in roots:
        move = chess.Move.from_uci(root[0])
        if root[2] not in {"proved", "unknown", "outside"}:
            return False
        if move not in board.legal_moves or not board.is_capture(move):
            return False
        if _detail(board, move, root[2]) != root:
            return False
    return True


def links(db, state):
    pairs = {
        (turn["position_id"], item["id"])
        for item in _items(state)
        for turn in (item.get("root_details") or {}).get("turns", ())
    }
    ids = {position for position, _ in pairs}
    if len(ids) != len(pairs):
        return False
    found = set()
    ids = list(ids)
    for start in range(0, len(ids), 400):
        batch = ids[start : start + 400]
        marks = ",".join("?" for _ in batch)
        found.update(
            tuple(row)
            for row in db.connection.execute(
                f"SELECT id,game_id FROM positions WHERE id IN ({marks})", batch
            )
        )
    return found == pairs


def _game(db, learner, item):
    turns = (item.get("root_details") or {}).get("turns", ())
    if not turns:
        return True
    source = prepare(db, learner, item["id"])
    if (source["identity"], fingerprint(source["signature"])) != (
        item["identity"],
        item["signature"],
    ):
        return False
    pairs = {
        context["position_id"]: (context, board)
        for context, board in source["pairs"]
        if context["subject"]
    }
    for turn in turns:
        pair = pairs.get(turn["position_id"])
        if pair is None or not _turn_matches(turn, *pair):
            return False
    return True


def matches(db, learner, games):
    return all(_game(db, learner, item) for item in games)
