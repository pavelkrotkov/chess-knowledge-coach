"""Resolve the attributable learner decision from reconstructed history."""

from .learner_context import decision_contexts


class NotLearnerDecision(ValueError):
    """The reconstructed mover is not the configured learner."""


def context_for_position(db, game_id, position_id, learner):
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
