"""Bound game-history work for one automatic scheduling invocation."""

from contextlib import contextmanager
from contextvars import ContextVar

from .ingest_reader import SilentGameBuilder
from .style_schedule_clock import DEADLINE, reached

CURRENT: ContextVar[dict[str, int] | None] = ContextVar(
    "style_schedule_history_budget", default=None
)
LIMIT = 2000
GAME_LIMIT = 1000


class BudgetExceeded(Exception):
    """The current scheduling invocation cannot safely reconstruct more history."""


class GameLimitExceeded(BudgetExceeded):
    """One game exceeds the per-game reconstruction ceiling."""


class LimitedBuilder(SilentGameBuilder):
    def __init__(self):
        super().__init__()
        self.seen = 0

    def visit_move(self, board, move):
        self.seen += 1
        if self.seen > GAME_LIMIT:
            raise GameLimitExceeded("game history limit")
        consume()
        return super().visit_move(board, move)


def consume():
    budget = CURRENT.get()
    if budget is not None:
        if reached():
            raise BudgetExceeded("worker deadline")
        if budget["used"] >= budget["limit"]:
            raise BudgetExceeded("invocation history limit")
        budget["used"] += 1


@contextmanager
def history_budget(*, deadline=None):
    budget = {"used": 0, "limit": LIMIT}
    token = CURRENT.set(budget)
    deadline_token = DEADLINE.set(deadline)
    try:
        yield budget
    finally:
        DEADLINE.reset(deadline_token)
        CURRENT.reset(token)
