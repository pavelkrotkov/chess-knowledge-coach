"""Validate the explicit optional curriculum goal and wall-clock window."""

from datetime import UTC, datetime

from .curriculum_priority_cursor import bind_goal
from .curriculum_window_options import GOALS
from .curriculum_window_options import MAX_MINUTES as MAX_MINUTES
from .curriculum_window_options import options as options
from .curriculum_window_value import envelope
from .mastery_time import parse_utc

POLICY = "curriculum-goal-window-v1"


def clock():
    return datetime.now(UTC)


def create(state, goal, minutes, page_limit, *, reset_turn=True):
    goal, minutes = options(goal, minutes)
    issued = clock()
    turn = GOALS[goal]
    bind_goal(state, goal)
    if reset_turn and turn is not None:
        state["family_turn"] = turn
    return envelope(state, goal, minutes, page_limit, issued, POLICY)


def expired(value):
    deadline = parse_utc(value["expires_at"])
    return deadline is not None and clock() >= deadline
