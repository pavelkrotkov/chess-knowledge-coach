"""Collect source-linked observations using one history replay per game."""

from .style_history import selected_boards
from .style_observation_detail import observation
from .style_opening import current_opening


def collect(db, learner, game, selected, by_id, counts, observations):
    opening = current_opening(db, game["game_id"])
    boards = selected_boards(db, game["game_id"], by_id.keys())
    for context in game["contexts"]:
        item = by_id.get(context["position_id"])
        if item is None:
            continue
        status, result, covered, completed = observation(
            db, learner, context, item, selected, opening, boards.get(context["position_id"])
        )
        counts[status] += 1
        counts["played_root_covered"] += covered
        counts["completed"] += completed
        if result:
            observations.append(result)
