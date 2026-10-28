"""Group consecutive game positions into structure episodes."""

from __future__ import annotations

from sqlite3 import Row

import chess

from .classification_transaction import classification_transaction
from .db import Database
from .structure_features import extract_features
from .structure_history import persist_episodes

DETECTOR_VERSION = "0.1.0"


def extract_game_episodes(
    db: Database,
    game_id: int,
    *,
    detector_version: str = DETECTOR_VERSION,
) -> int:
    """Extract contiguous same-feature episodes for a stored Standard game."""
    if not isinstance(detector_version, str) or not detector_version.strip():
        raise ValueError("detector version must be nonempty")
    with classification_transaction(db):
        game = db.connection.execute(
            "SELECT variant FROM games WHERE id = ?", (game_id,)
        ).fetchone()
        if game is None:
            raise ValueError(f"unknown game id: {game_id}")
        if game["variant"] != "Standard":
            raise ValueError(f"structure extraction does not support variant {game['variant']!r}")
        rows = db.connection.execute(
            "SELECT ply, fen FROM positions WHERE game_id = ? ORDER BY ply", (game_id,)
        ).fetchall()
        episodes = _group_episodes(rows)
        return persist_episodes(db, game_id, detector_version, rows, episodes)


def _group_episodes(rows: list[Row]) -> list[tuple[int, int, dict[str, object]]]:
    episodes: list[tuple[int, int, dict[str, object]]] = []
    for row in rows:
        features = extract_features(chess.Board(row["fen"]))
        if episodes and episodes[-1][2] == features and episodes[-1][1] + 1 == row["ply"]:
            episodes[-1] = (episodes[-1][0], row["ply"], features)
        else:
            episodes.append((row["ply"], row["ply"], features))
    return episodes
