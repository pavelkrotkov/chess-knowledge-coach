"""Check bounded scan candidates without replaying the lesson proof."""

from .material_context import NotLearnerDecision, context_for_position
from .material_source_marker import source_marker
from .rook_plan_cache_facts import detector
from .rook_plan_cache_mapping import valid


def _matches(inputs, marker, context):
    return (
        inputs["source_marker"] == marker
        and inputs["pre_move_fen"] == context["pre_move_fen"]
        and inputs["played_move"] == context["played_move"]
    )


def state(db, position_id, learner, *, _history=None):
    position = db.connection.execute(
        "SELECT game_id FROM positions WHERE id=?", (position_id,)
    ).fetchone()
    if position is None:
        return "unavailable"
    try:
        context = context_for_position(
            db, position["game_id"], position_id, learner, _history=_history
        )
        stored = detector(db, position_id)
        if stored is None:
            return "needed"
        run, inputs, facts, payloads = stored
        marker = source_marker(db, position_id, position["game_id"], learner)
        if not _matches(inputs, marker, context):
            return "needed"
        return (
            "current"
            if valid(db, position_id, context, position["game_id"], run, inputs, facts, payloads)
            else "needed"
        )
    except NotLearnerDecision:
        return "opponent"
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        return "unavailable"
