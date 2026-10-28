"""Record Maia predictions separately from canonical chess facts."""

from __future__ import annotations

import json
from sqlite3 import Row
from typing import Any

import chess

from .db import Database
from .maia_adapter import UnavailableMaiaAdapter
from .maia_probabilities import _validate_probabilities


def predict_maia(db: Database | None, position_id: int, adapter: Any) -> dict[str, Any] | None:
    if isinstance(adapter, UnavailableMaiaAdapter) or db is None:
        return None
    position, moves, elo = _prediction_context(db, position_id)
    probabilities = adapter.predict(position["fen"], moves, elo)
    _validate_probabilities(probabilities)
    adapter_version = getattr(adapter, "adapter_version", "custom-0.1.0")
    db.connection.execute(
        """INSERT INTO maia_predictions
        (position_id, model, checkpoint, adapter_version, conditioning_elo, probabilities_json)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (
            position_id,
            adapter.model,
            adapter.checkpoint,
            adapter_version,
            elo,
            json.dumps(probabilities, sort_keys=True, allow_nan=False),
        ),
    )
    db.connection.commit()
    return {
        "model": adapter.model,
        "checkpoint": adapter.checkpoint,
        "adapter_version": adapter_version,
        "conditioning_elo": elo,
        "probabilities": probabilities,
    }


def _prediction_context(db: Database, position_id: int) -> tuple[Row, list[str], int | None]:
    position = db.connection.execute(
        "SELECT * FROM positions WHERE id = ?", (position_id,)
    ).fetchone()
    if position is None:
        raise ValueError(f"unknown position id: {position_id}")
    moves = [
        row["uci"]
        for row in db.connection.execute(
            "SELECT uci FROM positions WHERE game_id = ? AND ply <= ? ORDER BY ply",
            (position["game_id"], position["ply"]),
        )
    ]
    game = db.connection.execute(
        "SELECT white_elo, black_elo FROM games WHERE id = ?", (position["game_id"],)
    ).fetchone()
    elo = None
    if game is not None:
        elo = game["white_elo"] if chess.Board(position["fen"]).turn else game["black_elo"]
    return position, moves, elo
