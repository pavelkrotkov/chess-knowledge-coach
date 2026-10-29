"""Resolve the attributable learner decision from reconstructed history."""

from .learner_context import decision_contexts
from .learner_identity import normalize_identity


class NotLearnerDecision(ValueError):
    """The reconstructed mover is not the configured learner."""


def context_for_position(db, game_id, position_id, learner, *, _history=None):
    if _history is not None:
        if _history.db is not db or normalize_identity(_history.learner) != normalize_identity(
            learner
        ):
            raise ValueError("history scope differs")
        return _history.context(game_id, position_id)
    context = next(
        (
            item
            for item in decision_contexts(db, game_id, learner=learner)
            if item["position_id"] == position_id
        ),
        None,
    )
    if context is None or context["subject"] is None:
        raise NotLearnerDecision("not a learner decision")
    return context
