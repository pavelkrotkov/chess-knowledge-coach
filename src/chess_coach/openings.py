"""Versioned opening dataset import and transposition-aware classification."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import chess

from .db import Database


def position_key(board: chess.Board) -> str:
    """Return a transposition-stable identity excluding move counters."""
    return " ".join(board.fen().split()[:4])


def _rows(path: str | Path) -> list[dict[str, str]]:
    text = Path(path).read_text(encoding="utf-8")
    if Path(path).suffix.lower() == ".json":
        payload = json.loads(text)
        return payload if isinstance(payload, list) else payload["openings"]
    return list(csv.DictReader(io.StringIO(text), dialect="excel-tab"))


def import_openings(
    db: Database,
    path: str | Path,
    *,
    version: str,
    source_url: str,
) -> int:
    """Import rows with ECO/name/moves columns into a versioned position DAG."""
    dataset = db.connection.execute(
        "INSERT OR IGNORE INTO opening_datasets(version, source_url) VALUES (?, ?)",
        (version, source_url),
    )
    dataset_id = (
        dataset.lastrowid
        or db.connection.execute(
            "SELECT id FROM opening_datasets WHERE version = ? AND source_url = ?",
            (version, source_url),
        ).fetchone()[0]
    )
    imported = 0
    for row in _rows(path):
        board = chess.Board()
        parent = position_key(board)
        for ply, san in enumerate(row["moves"].split(), start=1):
            move = board.parse_san(san)
            board.push(move)
            child = position_key(board)
            db.connection.execute(
                "INSERT OR IGNORE INTO opening_edges(dataset_id, parent_key, child_key, uci) VALUES (?, ?, ?, ?)",
                (dataset_id, parent, child, move.uci()),
            )
            db.connection.execute(
                """INSERT OR IGNORE INTO opening_nodes
                (dataset_id, position_key, eco, name, ply) VALUES (?, ?, ?, ?, ?)""",
                (dataset_id, child, row.get("eco"), row["name"], ply),
            )
            parent = child
        imported += 1
    db.connection.commit()
    return imported


def classify_game(
    db: Database, game_id: int, *, version: str, source_url: str
) -> dict[str, object]:
    dataset = db.connection.execute(
        "SELECT id FROM opening_datasets WHERE version = ? AND source_url = ?",
        (version, source_url),
    ).fetchone()
    if dataset is None:
        raise ValueError(f"opening dataset {version!r} is not imported")
    dataset_id = dataset[0]
    best = None
    for position in db.connection.execute(
        "SELECT ply, fen FROM positions WHERE game_id = ? ORDER BY ply", (game_id,)
    ):
        key = " ".join(position["fen"].split()[:4])
        node = db.connection.execute(
            """SELECT id, eco, name, ply FROM opening_nodes
            WHERE dataset_id = ? AND position_key = ? ORDER BY ply DESC LIMIT 1""",
            (dataset_id, key),
        ).fetchone()
        if node is not None and (best is None or node["ply"] > best["ply"]):
            best = node
    db.connection.execute(
        "DELETE FROM game_openings WHERE game_id = ? AND dataset_id = ?", (game_id, dataset_id)
    )
    if best is None:
        db.connection.commit()
        return {"matched": False, "confidence": 0.0}
    db.connection.execute(
        "INSERT INTO game_openings(game_id, dataset_id, opening_node_id, confidence) VALUES (?, ?, ?, ?)",
        (game_id, dataset_id, best["id"], 1.0),
    )
    db.connection.commit()
    return {"matched": True, "eco": best["eco"], "name": best["name"], "confidence": 1.0}
