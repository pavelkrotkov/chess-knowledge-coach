"""Reconstruct learner-attributed game decisions for mastery."""

from __future__ import annotations

from typing import Any, cast

from .db import Database
from .learner_context import decision_contexts


def decisions_for_game(
    db: Database, game_id: int, subject: str
) -> dict[int, dict[str, Any]] | None:
    try:
        contexts = list(decision_contexts(db, game_id, learner=subject))
        return {cast(int, context["position_id"]): context for context in contexts}
    except (ValueError, TypeError):
        return None
