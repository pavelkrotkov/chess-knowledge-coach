"""Prepare fork verification outside the atomic publication transaction."""

from .fork_observation import observe
from .fork_publish import publish
from .fork_replay import current_result
from .material_source import prepare
from .material_source_marker import source_marker


def process_decision(db, position_id, learner):
    if db.connection.in_transaction:
        raise RuntimeError("fork detection requires an idle database")
    prepared = prepare(db, position_id, learner)
    replay = current_result(db, prepared)
    if replay is not None:
        if (
            source_marker(db, position_id, prepared["game_id"], learner)
            != prepared["source_marker"]
        ):
            raise ValueError("fork source changed")
        return replay
    fact = observe(
        prepared["board"], prepared["context"]["played_move"], prepared["best"], prepared["played"]
    )
    return publish(db, prepared, fact)
