"""Resolve a current attributable decision and its provisional pawn lesson."""

from .material_source import prepare
from .rook_plan_lesson import lesson


def prepare_lesson(db, position_id, learner):
    prepared = prepare(db, position_id, learner)
    result = lesson(
        prepared["board"], prepared["context"]["played_move"], prepared["best"], prepared["played"]
    )
    return prepared, result


def current_lesson(db, position_id, learner):
    try:
        prepared, result = prepare_lesson(db, position_id, learner)
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
    if result is None:
        return None
    return {**result, "provenance": prepared["provenance"], "position_id": position_id}
