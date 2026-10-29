"""Prepare fork-defense verification outside atomic publication."""

from .fork_defense_contract import FACT_TYPE, MAPPER, PRODUCER, VERSION
from .fork_defense_mapping import mapping
from .fork_defense_observation import observe
from .fork_publish import publish
from .fork_replay import current_result
from .fork_storage import fact_run
from .material_source import prepare
from .material_source_marker import source_marker


def process_decision(db, position_id, learner):
    if db.connection.in_transaction:
        raise RuntimeError("fork defense detection requires an idle database")
    prepared = prepare(db, position_id, learner)
    replay = current_result(
        db, prepared, producer=PRODUCER, version=VERSION, fact_type=FACT_TYPE, mapper=MAPPER
    )
    if replay is not None:
        if (
            source_marker(db, position_id, prepared["game_id"], learner)
            != prepared["source_marker"]
        ):
            raise ValueError("fork defense source changed")
        return replay
    fact = observe(
        prepared["board"], prepared["context"]["played_move"], prepared["best"], prepared["played"]
    )
    return publish(db, prepared, fact, fact_writer=_fact_run, mapping_writer=mapping)


def _fact_run(db, position_id, inputs, fact):
    return fact_run(
        db, position_id, inputs, fact, producer=PRODUCER, version=VERSION, fact_type=FACT_TYPE
    )
