"""Scoring and observation-time handling for mastery."""

from datetime import UTC, datetime
from typing import Any


def _score(rows: list[Any]) -> tuple[float, float]:
    effective = [row for row in rows if row["outcome"] in {"success", "failure"}]
    weight = sum(row["confidence"] for row in effective)
    score = (
        sum(row["confidence"] for row in effective if row["outcome"] == "success") / weight
        if weight
        else 0.5
    )
    return score, weight


def _observation_time(row: Any) -> datetime | None:
    if row["observation_at"] is None:
        return None
    try:
        value = datetime.fromisoformat(row["observation_at"])
    except ValueError:
        return datetime.now(UTC)
    return value if value.tzinfo else value.replace(tzinfo=UTC)
