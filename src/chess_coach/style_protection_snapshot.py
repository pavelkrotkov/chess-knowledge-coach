"""Rebind compared analysis and source in one read-only decision snapshot."""

from .deep_execution_views import deep_for_position
from .preview_snapshot import preview_history
from .style_protection_budget import take
from .style_protection_collect import collect
from .style_protection_source import reference


def inspect(db, learner, context, board, deep, compared, budget, *, history=None):
    if not take(budget, "lookups"):
        return None
    # A missing reference stays unknown; it is never a negative threat finding.
    evidence, reason = reference(db, learner, context["position_id"])
    if evidence is None:
        budget[reason] += 1
        return None
    if not take(budget, "resolutions"):
        return None
    try:
        if history is not None:
            return _within(db, learner, context, board, deep, compared, evidence, budget, history)
        with preview_history(db, learner) as history:
            history.targets([context["position_id"]])
            return _within(db, learner, context, board, deep, compared, evidence, budget, history)
    except (ValueError, TypeError, KeyError, IndexError):
        return None


def _within(db, learner, context, board, deep, compared, evidence, budget, history):
    # Rebind the exact board and engine result to the same read-only snapshot.
    fresh = history.board(context["game_id"], context["position_id"])
    if not _same_history(fresh, board) or not _same_deep(
        db, learner, context, fresh, deep, history
    ):
        return None
    if not take(budget, "lookups"):
        return None
    if reference(db, learner, context["position_id"]) != (evidence, None):
        return None
    return collect(db, learner, context, fresh, compared, evidence, budget, history=history)


def _same_history(fresh, board):
    return fresh.fen() == board.fen() and fresh.move_stack == board.move_stack


def _same_deep(db, learner, context, board, deep, history):
    return (
        deep_for_position(
            db, context["position_id"], learner, board, context["played_move"], _history=history
        )
        == deep
    )
