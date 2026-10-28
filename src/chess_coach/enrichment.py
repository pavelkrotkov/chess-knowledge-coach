"""Optional Maia and LLM enrichments kept downstream of canonical chess facts."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .db import Database
from .maia_adapter import MaiaAdapter as MaiaAdapter
from .maia_adapter import SubprocessMaiaAdapter as SubprocessMaiaAdapter
from .maia_adapter import UnavailableMaiaAdapter as UnavailableMaiaAdapter
from .maia_predictions import predict_maia as predict_maia


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
