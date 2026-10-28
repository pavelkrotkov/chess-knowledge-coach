"""Validate probability maps returned by Maia adapters."""

from __future__ import annotations

import json
import math
from typing import Any


def _parse_probabilities(stdout: str) -> dict[str, float]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Maia adapter returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Maia adapter returned a non-object response")
    if not _has_probability_format(payload):
        raise ValueError("Maia adapter returned invalid probability format")
    probabilities = {key: float(value) for key, value in payload.items()}
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities.values()):
        raise ValueError("Maia adapter probabilities must be finite values in [0, 1]")
    return probabilities


def _validate_probabilities(probabilities: Any) -> None:
    if not isinstance(probabilities, dict) or not all(
        isinstance(key, str)
        and isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
        and 0 <= float(value) <= 1
        for key, value in probabilities.items()
    ):
        raise ValueError("Maia adapter probabilities must be finite values in [0, 1]")


def _has_probability_format(payload: dict[Any, Any]) -> bool:
    return all(
        isinstance(key, str) and isinstance(value, (int, float)) and not isinstance(value, bool)
        for key, value in payload.items()
    )
