"""Group consecutive game positions into structure episodes."""

from __future__ import annotations

import json
from sqlite3 import Row

import chess

from .db import Database
from .structure_features import _structure_names, extract_features

DETECTOR_VERSION = "0.1.0"


def extract_game_episodes(
    db: Database,
    game_id: int,
    *,
    detector_version: str = DETECTOR_VERSION,
) -> int:
    """Extract contiguous same-feature episodes for a stored Standard game."""
    game = db.connection.execute("SELECT variant FROM games WHERE id = ?", (game_id,)).fetchone()
    if game is None:
        raise ValueError(f"unknown game id: {game_id}")
    if game["variant"] != "Standard":
        raise ValueError(f"structure extraction does not support variant {game['variant']!r}")
    rows = db.connection.execute(
        "SELECT ply, fen FROM positions WHERE game_id = ? ORDER BY ply", (game_id,)
    ).fetchall()
    db.connection.execute(
        "DELETE FROM structure_episodes WHERE game_id = ? AND detector_version = ?",
        (game_id, detector_version),
    )
    episodes = _group_episodes(rows)
    for start, end, features in episodes:
        db.connection.execute(
            """INSERT INTO structure_episodes
            (game_id, start_ply, end_ply, features_json, structure_json, confidence, detector_version)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                game_id,
                start,
                end,
                json.dumps(features, sort_keys=True),
                json.dumps(_structure_names(features)),
                1.0,
                detector_version,
            ),
        )
    db.connection.commit()
    return len(episodes)


def _group_episodes(rows: list[Row]) -> list[tuple[int, int, dict[str, object]]]:
    episodes: list[tuple[int, int, dict[str, object]]] = []
    for row in rows:
        features = extract_features(chess.Board(row["fen"]))
        if episodes and episodes[-1][2] == features and episodes[-1][1] + 1 == row["ply"]:
            episodes[-1] = (episodes[-1][0], row["ply"], features)
        else:
            episodes.append((row["ply"], row["ply"], features))
    return episodes
