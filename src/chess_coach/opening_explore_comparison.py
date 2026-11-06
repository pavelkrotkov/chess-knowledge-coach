"""Read a single selected exact-exemplar comparison for the profile."""

from .opening_queue_view import statuses
from .tactical_course_deadline import PreviewDeadline


def comparison(db, root, learner, exemplar, alternative):
    decision = {
        "game_id": exemplar["game_id"],
        "position_id": exemplar["position_id"],
        "catalog": {"items": [alternative]},
    }
    try:
        state = statuses(db, root, learner, decision).get(alternative["uci"], {})
    except (Exception, PreviewDeadline):
        return None
    if state.get("status") != "complete":
        return None
    lines = {line["root_move"]: line for line in state["lines"]}
    played, other = lines.get(exemplar["played_uci"]), lines.get(alternative["uci"])
    if played is None or other is None:
        return None
    return {
        "played": played["score_value"],
        "alternative": other["score_value"],
        "depth": played["depth"],
    }
