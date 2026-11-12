"""Validate bounded catalog continuations from one exact parent position."""

import chess

from .opening_storage import position_key

SCAN = 64
SHOW = 8


def _edge(board, row):
    try:
        move = chess.Move.from_uci(row["uci"])
        if move not in board.legal_moves:
            return None
        after = board.copy()
        san = after.san(move)
        after.push(move)
        if position_key(after) != row["child_key"]:
            return None
        return {"uci": move.uci(), "san": san, "child": row["child_key"]}
    except (ValueError, TypeError):
        return None


def catalog(db, dataset, board, played, *, alternative=None):
    parent = position_key(board)
    rows = db.connection.execute(
        """SELECT uci,child_key FROM opening_edges WHERE dataset_id=? AND parent_key=?
        AND uci<>? ORDER BY child_key,uci LIMIT ?""",
        (dataset, parent, played, SCAN + 1),
    ).fetchall()
    items = []
    for row in rows[:SCAN]:
        item = _edge(board, row)
        if item is not None:
            items.append(item)
    shown = items[:SHOW]
    shown.extend(item for item in items[SHOW:] if item["uci"] == alternative)
    return {
        "parent": parent,
        "items": shown,
        "truncated": len(rows) > SCAN or len(items) > SHOW,
    }
