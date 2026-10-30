"""Collect source-linked observations using one history replay per game."""

from .style_defense_coverage import record as record_check_context
from .style_history import selected_boards
from .style_observation_detail import observation
from .style_opening import current_opening


def collect(
    db, learner, game, selected, by_id, counts, observations, budget, *, boards=None, history=None
):
    opening = current_opening(db, game["game_id"])
    if boards is None:
        boards = selected_boards(db, game["game_id"], by_id.keys())
    for context in game["contexts"]:
        item = by_id.get(context["position_id"])
        if item is None:
            continue
        status, result, covered, completed = observation(
            db,
            learner,
            context,
            item,
            selected,
            opening,
            boards.get(context["position_id"]),
            budget,
            history=history,
        )
        record_check_context(counts, boards.get(context["position_id"]), context, status)
        counts[status] += 1
        counts["played_root_covered"] += covered
        counts["completed"] += completed
        if result:
            observations.append(result)
