"""Verify learner ownership and identify independent game contexts."""

from __future__ import annotations

from .db import Database
from .mastery_game_lookup import decisions_for_game
from .mastery_time import parse_utc


def game_context(db: Database, row, cache: dict[int, dict[int, dict[str, object]] | None]):
    reason = _identity_reason(row)
    if reason is not None:
        return None, reason
    game_id = row["game_id"]
    if game_id not in cache:
        cache[game_id] = decisions_for_game(db, game_id, row["subject"])
    decisions = cache[game_id]
    if decisions is None:
        return None, "invalid_game"
    decision = decisions.get(row["position_id"])
    if decision is None or decision["subject"] != row["subject"]:
        return None, "not_learner_decision"
    observed = parse_utc(row["observation_at"])
    source_time = parse_utc(decision["observation_at"])
    if source_time is None:
        return None, "unknown_source_time"
    if observed != source_time:
        return None, "observation_time_mismatch"
    return {
        "kind": "game",
        "prompt_fen": decision["prompt_fen"],
        "game_key": decision["game_key"],
        "game_id": game_id,
        "source": row["source"],
        "source_id": row["source_id"],
        "ply": row["ply"],
    }, None


def _identity_reason(row) -> str | None:
    if row["game_id"] is None:
        return "training_context_unavailable"
    if not row["source"] or not row["source_id"]:
        return "missing_game_identity"
    return None
