"""Recheck queue and public bindings under separate bounded history scopes."""

from .opening_public_proof_source import binding as proof_binding
from .opening_queue_binding import snapshot
from .style_schedule_budget import history_budget


def bindings(db, root, learner, decision, database, move, budget):
    with history_budget(deadline=budget.expires):
        _, source, config, _ = snapshot(
            db,
            database,
            learner,
            decision["game_id"],
            decision["position_id"],
            move,
            deadline=budget.expires,
            budget=budget,
        )
    with history_budget(deadline=budget.expires), budget.scope(snapshot=False):
        base, _ = proof_binding(
            db, root, learner, decision["game_id"], decision["position_id"], move, budget.expires
        )
    if base["source"] != source:
        raise ValueError("opening binding changed")
    return source, config, base
