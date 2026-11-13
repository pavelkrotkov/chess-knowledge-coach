"""Recheck a locally verified purpose board against one fresh database snapshot."""

from .purpose_source import inputs
from .purpose_source_binding import history_fingerprint
from .style_schedule_budget import BudgetExceeded
from .style_schedule_clock import reached


def _deadline():
    if reached():
        raise BudgetExceeded("worker deadline")


def recheck(db, position_id, learner, previous):
    if not db.connection.in_transaction:
        raise RuntimeError("purpose recheck requires a transaction")
    _deadline()
    key, position, game, color, rows = inputs(db, position_id, learner)
    fingerprint = history_fingerprint(game, color, rows)
    if not _same(previous, key, position, game, fingerprint):
        raise ValueError("verified source changed")
    board = previous["board"].copy(stack=True)
    _deadline()
    return {
        "game_id": game["id"],
        "position": position,
        "board": board,
        "learner_key": key,
        "fingerprint": fingerprint,
    }


# Read the game and all indexed plies in the caller's existing transaction.
def _same(previous, key, position, game, fingerprint):
    return (
        previous["game_id"] == game["id"]
        and previous["learner_key"] == key
        and dict(previous["position"]) == dict(position)
        and previous["fingerprint"] == fingerprint
    )
