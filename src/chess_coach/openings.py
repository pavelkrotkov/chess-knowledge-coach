"""Versioned opening dataset import and transposition-aware classification."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import chess
import chess.pgn

from .db import Database


def position_key(board: chess.Board) -> str:
    """Return a transposition-stable identity excluding move counters."""
    return " ".join(board.fen().split()[:4])


def _rows(path: str | Path) -> list[dict[str, str]]:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            payload = json.loads(text)
            rows = payload if isinstance(payload, list) else payload["openings"]
        else:
            rows = list(csv.DictReader(io.StringIO(text), dialect="excel-tab"))
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"failed to read opening dataset {path}: {exc}") from exc
    if not isinstance(rows, list):
        raise ValueError(f"opening dataset {path} must contain a list of rows")
    return rows


def _moves(row: dict[str, str]) -> list[chess.Move]:
    text = row.get("moves") or row.get("pgn")
    if not text:
        raise ValueError("opening row requires a moves or pgn field")
    if row.get("pgn"):
        game = chess.pgn.read_game(io.StringIO(text))
        if game is None:
            raise ValueError("opening row contains an empty PGN")
        return [node.move for node in game.mainline()]
    board = chess.Board()
    moves = []
    for token in text.split():
        moves.append(board.parse_san(token))
        board.push(moves[-1])
    return moves


def import_openings(
    db: Database,
    path: str | Path,
    *,
    version: str,
    source_url: str,
) -> int:
    """Import ECO/name/moves or ECO/name/pgn rows into a position DAG."""
    try:
        db.connection.execute(
            "INSERT OR IGNORE INTO opening_datasets(version, source_url) VALUES (?, ?)",
            (version, source_url),
        )
        dataset_id = db.connection.execute(
            "SELECT id FROM opening_datasets WHERE version = ? AND source_url = ?",
            (version, source_url),
        ).fetchone()
        if dataset_id is None:
            raise ValueError(f"failed to insert or find dataset {version!r}")
        dataset_id = dataset_id[0]
        imported = 0
        for row in _rows(path):
            name = row.get("name")
            if not name:
                raise ValueError("opening row requires a name field")
            board = chess.Board()
            parent = position_key(board)
            moves = _moves(row)
            for move in moves:
                board.push(move)
                child = position_key(board)
                db.connection.execute(
                    """INSERT OR IGNORE INTO opening_edges
                    (dataset_id, parent_key, child_key, uci) VALUES (?, ?, ?, ?)""",
                    (dataset_id, parent, child, move.uci()),
                )
                parent = child
            if not moves:
                raise ValueError("opening row requires at least one move")
            db.connection.execute(
                """INSERT OR IGNORE INTO opening_nodes
                (dataset_id, position_key, eco, name, ply) VALUES (?, ?, ?, ?, ?)""",
                (dataset_id, parent, row.get("eco"), name, len(moves)),
            )
            imported += 1
        db.connection.commit()
        return imported
    except Exception:
        db.connection.rollback()
        raise


def classify_game(
    db: Database, game_id: int, *, version: str, source_url: str
) -> dict[str, object]:
    game = db.connection.execute("SELECT variant FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        raise ValueError(f"unknown game id: {game_id}")
    if game["variant"] != "Standard":
        raise ValueError(f"opening classification does not support variant {game['variant']!r}")
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
