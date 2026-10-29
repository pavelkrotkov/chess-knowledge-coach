"""Determine remaining mate plies from the accepted immutable event prefix."""

from .objective_events import response
from .objective_short_final import judge as judge_final
from .objective_short_judge import judge as judge_short


def remaining(board, request, events):
    color = "white" if board.turn else "black"
    if color != request["learner_color"]:
        return None
    matched = [
        response(event) for event in events[:-1] if response(event).get("feedback") == "line_match"
    ]
    if not matched:
        return 3
    if len(matched) == 1 and matched[0].get("opponent_move"):
        return 1
    return None


def verify(board, move, request, events, clock, start, seconds, base):
    plies = remaining(board, request, events)
    if plies is None:
        return {**base, "status": "unresolved", "reason": "objective_horizon_changed"}
    if plies == 1:
        return judge_final(board, move, clock, start, seconds, base)
    return judge_short(board, move, clock, start, seconds, base)
