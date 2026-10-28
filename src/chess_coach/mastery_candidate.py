"""Validate and construct one candidate independent game context."""

from __future__ import annotations

from datetime import datetime
from typing import cast

from .db import Database
from .mastery_checks import basic_reason
from .mastery_game_context import game_context
from .mastery_time import parse_utc

HORIZON_DAYS = 365


def prepare_candidate(db: Database, row, subject: str, as_of: datetime, cache: dict):
    reason = basic_reason(row, subject)
    if reason is not None:
        return None, reason
    observed = parse_utc(row["observation_at"])
    reason = _time_reason(observed, as_of)
    if reason is not None:
        return None, reason
    context, reason = game_context(db, row, cache)
    if reason is not None:
        return None, reason
    observed = cast(datetime, observed)
    context = cast(dict, context)
    age = (as_of.date() - observed.date()).days
    item = {
        "evidence_id": row["id"],
        "outcome": row["outcome"],
        "confidence": float(row["confidence"]),
        "observed_at": observed.isoformat(),
        "age_days": age,
        "context": context,
        "ply": row["ply"],
    }
    return item, None


def _time_reason(observed: datetime | None, as_of: datetime) -> str | None:
    if observed is None:
        return "unknown_or_invalid_time"
    if observed > as_of:
        return "future_observation"
    if (as_of.date() - observed.date()).days > HORIZON_DAYS:
        return "outside_horizon"
    return None
