"""Store opening positions and edges from parsed rows."""

from __future__ import annotations

import chess

from .db import Database
from .opening_rows import _moves


def position_key(board: chess.Board) -> str:
    """Return a transposition-stable identity excluding move counters."""
    return " ".join(board.fen().split()[:4])


def _import_row(db: Database, dataset_id: int, row: dict[str, str], row_number: int) -> None:
    name = row.get("name") or row.get("Name")
    if not name:
        raise ValueError(f"opening row {row_number} requires a name field")
    try:
        moves = _moves(row)
    except ValueError as exc:
        raise ValueError(f"opening row {row_number}: {exc}") from exc
    if not moves:
        raise ValueError(f"opening row {row_number} requires at least one move")
    board = chess.Board()
    parent = position_key(board)
    for move in moves:
        board.push(move)
        child = position_key(board)
        db.connection.execute(
            """INSERT OR IGNORE INTO opening_edges
            (dataset_id, parent_key, child_key, uci) VALUES (?, ?, ?, ?)""",
            (dataset_id, parent, child, move.uci()),
        )
        parent = child
    db.connection.execute(
        """INSERT OR IGNORE INTO opening_nodes
        (dataset_id, position_key, eco, name, ply) VALUES (?, ?, ?, ?, ?)""",
        (dataset_id, parent, row.get("eco"), name, len(moves)),
    )
