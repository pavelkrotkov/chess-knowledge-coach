"""Prepare bounded back-rank observations from current learner decisions."""

from .back_rank_attack import prove
from .back_rank_candidate import candidate
from .back_rank_defense import observe
from .back_rank_inputs import inputs
from .back_rank_publish import publish
from .back_rank_replay import replay
from .mate_inspection_source import checked_board, position_row
from .mate_proof_moves import move_view
from .material_context import context_for_position


def process_decision(db, position_id, learner):
    if db.connection.in_transaction:
        raise RuntimeError("back-rank detection requires an idle database")
    position = position_row(db, position_id)
    context = context_for_position(db, position["game_id"], position_id, learner)
    snapshot, key, proof = inputs(db, position, context["subject"])
    board = checked_board(db, position, snapshot)
    prior = replay(db, position_id, key, context["subject"])
    if prior:
        if inputs(db, position, context["subject"])[1] != key:
            raise ValueError("back-rank source changed")
        return prior
    fact = _observe(board, board.parse_uci(position["uci"]), proof)
    return publish(db, position, key, fact, context)


def _observe(board, played, proof):
    if proof and candidate(board, not board.turn):
        attack = prove(board, proof)
    else:
        attack = {"status": "unknown", "reason": "mate_proof_or_geometry_unavailable"}
    if candidate(board, board.turn):
        defense = observe(board, played)
    else:
        defense = {"status": "unknown", "reason": "back_rank_geometry_not_selected"}
    return {
        "played": played.uci(),
        "played_san": move_view(board, played)["san"],
        "attack": attack,
        "defense": defense,
    }
