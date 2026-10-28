"""Transparent uncalibrated outcome weighting by whole UTC days."""

from __future__ import annotations

from typing import Any

MIN_CONTEXTS = 3
HALF_LIFE_DAYS = 90
RECENT_DAYS = 30
POLICY_VERSION = "mastery-v2-90d"


def calculate(items: list[dict]) -> dict[str, Any]:
    weighted = _weighted(items)
    total = sum(item["weight"] for item in weighted)
    return {
        "status": "sufficient" if len(weighted) >= MIN_CONTEXTS else "insufficient",
        "context_count": len(weighted),
        "mastery": _score(weighted) if len(weighted) >= MIN_CONTEXTS else None,
        "effective_weight": total,
        "uncertainty": 1 / (1 + total),
        "trend_30d": _trend(weighted) if len(weighted) >= MIN_CONTEXTS else None,
        "supporting_evidence_ids": [item["evidence_id"] for item in weighted],
        "contexts": weighted,
    }


def _score(items: list[dict]) -> float:
    total = sum(item["weight"] for item in items)
    return sum(item["weight"] for item in items if item["outcome"] == "success") / total


def _weighted(items: list[dict]) -> list[dict]:
    return [
        {**item, "weight": item["confidence"] * 2 ** (-item["age_days"] / HALF_LIFE_DAYS)}
        for item in items
    ]


def _trend(items: list[dict]) -> float | None:
    recent = [item for item in items if item["age_days"] <= RECENT_DAYS]
    older = [item for item in items if item["age_days"] > RECENT_DAYS]
    return _score(recent) - _score(older) if recent and older else None
