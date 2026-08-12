"""Optional Maia and LLM enrichments kept downstream of canonical chess facts."""

from __future__ import annotations

import json
import math
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

import chess

from .db import Database


class MaiaAdapter(Protocol):
    model: str
    checkpoint: str
    adapter_version: str

    def predict(self, fen: str, moves: list[str], elo: int | None = None) -> dict[str, float]: ...


@dataclass(frozen=True)
class UnavailableMaiaAdapter:
    model: str = "unavailable"
    checkpoint: str = "none"
    adapter_version: str = "offline-0.1.0"

    def predict(self, fen: str, moves: list[str], elo: int | None = None) -> dict[str, float]:
        raise RuntimeError("Maia is unavailable; install and configure the optional adapter")


@dataclass(frozen=True)
class SubprocessMaiaAdapter:
    executable: str
    model: str
    checkpoint: str
    adapter_version: str = "subprocess-0.1.0"
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if not self.checkpoint or self.checkpoint in {"configured", "none"}:
            raise ValueError("Maia checkpoint must be an explicit reproducible identifier")

    def predict(self, fen: str, moves: list[str], elo: int | None = None) -> dict[str, float]:
        try:
            completed = subprocess.run(
                [self.executable],
                input=json.dumps({"fen": fen, "moves": moves, "elo": elo}),
                text=True,
                capture_output=True,
                timeout=self.timeout_seconds,
                check=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Maia adapter failed: {exc}") from exc
        try:
            payload = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Maia adapter returned invalid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("Maia adapter returned a non-object response")
        if not all(
            isinstance(key, str) and isinstance(value, (int, float)) and not isinstance(value, bool)
            for key, value in payload.items()
        ):
            raise ValueError("Maia adapter returned invalid probability format")
        probabilities = {key: float(value) for key, value in payload.items()}
        if not all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities.values()):
            raise ValueError("Maia adapter probabilities must be finite values in [0, 1]")
        return probabilities


def predict_maia(db: Database | None, position_id: int, adapter: Any) -> dict[str, Any] | None:
    if isinstance(adapter, UnavailableMaiaAdapter) or db is None:
        return None
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
    probabilities = adapter.predict(position["fen"], moves, elo)
    if not isinstance(probabilities, dict) or not all(
        isinstance(key, str)
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0 <= float(value) <= 1
        for key, value in probabilities.items()
    ):
        raise ValueError("Maia adapter probabilities must be finite values in [0, 1]")
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


def explain_position(
    db: Database,
    position_id: int,
    *,
    facts: dict[str, Any],
    generator: Callable[[dict[str, Any]], str],
    model: str = "configured-llm",
    prompt_version: str = "facts-only-v1",
) -> dict[str, Any]:
    position = db.connection.execute(
        "SELECT id FROM positions WHERE id = ?", (position_id,)
    ).fetchone()
    if position is None:
        raise ValueError(f"unknown position id: {position_id}")
    prompt_json = json.dumps({"facts": facts}, sort_keys=True, allow_nan=False)
    response = generator({"facts": facts})
    if not isinstance(response, str):
        raise ValueError("LLM generator must return text")
    db.connection.execute(
        """INSERT INTO llm_explanations
        (position_id, model, prompt_version, prompt_json, response)
        VALUES (?, ?, ?, ?, ?)""",
        (position_id, model, prompt_version, prompt_json, response),
    )
    db.connection.commit()
    return {
        "model": model,
        "prompt_version": prompt_version,
        "prompt_json": prompt_json,
        "response": response,
    }
