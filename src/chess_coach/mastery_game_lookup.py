"""Reconstruct learner-attributed game decisions for mastery."""

from __future__ import annotations

from typing import Any, cast

import chess

from .db import Database
from .learner_context import decision_contexts
from .mastery_game_identity import game_identity
from .mastery_position import position_key


def decisions_for_game(
    db: Database, game_id: int, subject: str, *, _history=None, _position_id=None
) -> dict[int, dict[str, Any]] | None:
    try:
        contexts = (
            list(decision_contexts(db, game_id, learner=subject))
            if _history is None
            else _history.contexts(db, subject, game_id, _position_id)
        )
        for context in contexts:
            context["prompt_fen"] = position_key(chess.Board(cast(str, context["pre_move_fen"])))
        identity = game_identity(db, game_id, contexts)
        return {
            cast(int, context["position_id"]): {**context, "game_key": identity}
            for context in contexts
        }
    except (ValueError, TypeError, IndexError):
        return None
