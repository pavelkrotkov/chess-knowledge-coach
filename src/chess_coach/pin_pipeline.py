"""Publish separate provisional pin execute and prevent observations."""

from functools import partial

from .fork_publish import publish
from .fork_replay import current_result
from .fork_storage import fact_run
from .mapping_runs import record_mapping_run_in_transaction
from .material_source import prepare
from .material_source_marker import source_marker
from .pin_defense import observe as defense
from .pin_observation import observe as execute

VERSION = "1.0.1"


def process_decision(db, position_id, learner, operation):
    if db.connection.in_transaction:
        raise RuntimeError("pin detection requires an idle database")
    prepared = prepare(db, position_id, learner)
    producer, mapper, fact_type = _names(operation)
    replay = current_result(
        db, prepared, producer=producer, version=VERSION, fact_type=fact_type, mapper=mapper
    )
    if replay is not None:
        if (
            source_marker(db, position_id, prepared["game_id"], learner)
            != prepared["source_marker"]
        ):
            raise ValueError("pin source changed")
        return replay
    observer = execute if operation == "execute" else defense
    fact = observer(
        prepared["board"], prepared["context"]["played_move"], prepared["best"], prepared["played"]
    )
    writer = partial(fact_run, producer=producer, version=VERSION, fact_type=fact_type)
    return publish(
        db,
        prepared,
        fact,
        fact_writer=writer,
        mapping_writer=partial(_mapping, operation=operation),
    )


def _names(operation):
    if operation not in {"execute", "prevent"}:
        raise ValueError("invalid pin operation")
    return f"pin-{operation}", f"pin-{operation}-mapper", f"pin_{operation}_opportunity"


def _mapping(db, prepared, inputs, run, fact, *, operation):
    if fact is None:
        return None
    context = prepared["context"]
    _, mapper, _ = _names(operation)
    details = {
        "game_id": prepared["game_id"],
        "ply": context["ply"],
        "pre_move_fen": context["pre_move_fen"],
        "played_move": context["played_move"],
        "pin_observation": fact,
        "provenance": prepared["provenance"],
        "qualification": "Provisional bounded observation; no intent or mastery inferred.",
    }
    item = {
        "skill": fact["kind"],
        "outcome": fact["outcome"],
        "confidence": 0.5,
        "fact_ids": run["fact_ids"],
        "context": details,
        "observation_at": context["observation_at"],
    }
    return record_mapping_run_in_transaction(
        db,
        position_id=prepared["position_id"],
        producer=mapper,
        mapper_version=VERSION,
        subject=context["subject"],
        operation=operation,
        scope_key=f"pin-{operation}-v1",
        input_data={
            "source": inputs,
            "fact_run": run["run_id"],
            "context": details,
            "observation_at": context["observation_at"],
        },
        mappings=[item],
    )
