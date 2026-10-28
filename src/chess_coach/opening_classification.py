"""Classify games against a versioned opening dataset."""

from __future__ import annotations

from .db import Database


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
    best = _best_match(db, game_id, dataset_id)
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


def _best_match(db: Database, game_id: int, dataset_id: int):
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
    return best
