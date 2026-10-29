"""Compute bounded mate facts from a current learner decision."""

from .mate_auto_publish import publish
from .mate_auto_replay import replay
from .mate_inspection_source import checked_board, position_row, source, still_current
from .mate_observation import observe
from .mate_selection import short_candidate
from .material_context import context_for_position


def process_decision(db, position_id, learner):
    if db.connection.in_transaction:
        raise RuntimeError("mate detection requires an idle database")
    position = position_row(db, position_id)
    context = context_for_position(db, position["game_id"], position_id, learner)
    snapshot, fingerprint = source(db, position, learner)
    board = checked_board(db, position, snapshot)
    prior = replay(db, position_id, fingerprint, context["subject"])
    if prior:
        if not still_current(db, position, learner, fingerprint):
            raise ValueError("mate source changed")
        return prior
    candidate = short_candidate(snapshot, position_id)
    fact = observe(board, board.parse_uci(position["uci"]), short_candidate=candidate)
    return publish(db, position, learner, fingerprint, fact, context)
