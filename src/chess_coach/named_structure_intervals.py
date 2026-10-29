"""Derive contiguous named intervals with their atomic sources."""

import chess

from .named_structures import match_structures

MAX_POSITIONS = 1000


def _rows(db, game_id):
    return db.connection.execute(
        """SELECT p.id position_id,p.ply,p.fen,e.id episode_id,
        e.run_id,e.detector_version FROM current_structure_episodes e
        JOIN positions p ON p.game_id=e.game_id AND p.ply BETWEEN e.start_ply AND e.end_ply
        WHERE e.game_id=? ORDER BY p.ply LIMIT ?""",
        (game_id, MAX_POSITIONS + 1),
    ).fetchall()


def _extend(intervals, match, row, game_id, learner_side):
    key = (match["family"], match["color"], match["square"])
    last = intervals.get(key)
    if last and last["end_ply"] + 1 == row["ply"]:
        last["end_ply"] = row["ply"]
        if row["episode_id"] not in last["episode_ids"]:
            last["episode_ids"].append(row["episode_id"])
        return None
    item = {
        **match,
        "game_id": game_id,
        "learner_color": learner_side,
        "start_ply": row["ply"],
        "end_ply": row["ply"],
        "position_id": row["position_id"],
        "episode_ids": [row["episode_id"]],
        "run_id": row["run_id"],
        "atomic_detector_version": row["detector_version"],
    }
    intervals[key] = item
    return item


def game_history(db, game_id, learner_side, version):
    rows = _rows(db, game_id)
    items, intervals = [], {}
    unknown = 0
    for row in rows[:MAX_POSITIONS]:
        matches = match_structures(chess.Board(row["fen"]), version=version)
        unknown += not bool(matches)
        for match in matches:
            item = _extend(intervals, match, row, game_id, learner_side)
            if item is not None:
                items.append(item)
    return items, unknown, len(rows) > MAX_POSITIONS
