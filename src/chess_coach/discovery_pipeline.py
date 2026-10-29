"""Publish owned discovered-attack decisions through the bounded worker."""

from functools import partial

from .discovery_contract import FACT, MAPPER, PRODUCER, SCOPE, VERSION
from .discovery_observation import observe
from .fork_publish import publish
from .fork_replay import current_result
from .fork_storage import fact_run
from .fork_worker import process_forks
from .fork_worker_cursor import scan
from .fork_worker_item import process_item
from .mapping_runs import record_mapping_run_in_transaction
from .material_source import prepare
from .material_source_marker import source_marker


def process_decision(db, position_id, learner):
    if db.connection.in_transaction:
        raise RuntimeError("discovery detection requires an idle database")
    prepared = prepare(db, position_id, learner)
    replay = current_result(
        db, prepared, producer=PRODUCER, mapper=MAPPER, version=VERSION, fact_type=FACT
    )
    if replay is not None:
        if (
            source_marker(db, position_id, prepared["game_id"], learner)
            != prepared["source_marker"]
        ):
            raise ValueError("discovery source changed")
        return replay
    fact = observe(
        prepared["board"], prepared["context"]["played_move"], prepared["best"], prepared["played"]
    )
    writer = partial(fact_run, producer=PRODUCER, version=VERSION, fact_type=FACT)
    return publish(db, prepared, fact, fact_writer=writer, mapping_writer=_mapping)


def _mapping(db, prepared, inputs, run, fact):
    if fact is None:
        return None
    context = prepared["context"]
    details = {
        "observation": fact,
        "provenance": prepared["provenance"],
        "qualification": "Provisional bounded observation; mastery is not inferred.",
    }
    item = {
        "skill": "discovered_attack",
        "outcome": fact["outcome"],
        "confidence": 0.5,
        "fact_ids": run["fact_ids"],
        "context": details,
        "observation_at": context["observation_at"],
    }
    return record_mapping_run_in_transaction(
        db,
        position_id=prepared["position_id"],
        producer=MAPPER,
        mapper_version=VERSION,
        subject=context["subject"],
        operation="execute",
        scope_key=SCOPE,
        input_data={"source": inputs, "fact_run": run["run_id"], "context": details},
        mappings=[item],
    )


def process_discoveries(db, config):
    policy = "discovery-execute-worker-v1"
    scanner = partial(scan, namespace="discovery-execute-cursor-v1:", policy=policy)
    processor = partial(process_item, detector=process_decision)
    report = process_forks(db, config, scanner=scanner, processor=processor, policy=policy)
    report["exclusions"] = {
        "unavailable": report["unavailable"],
        "ambiguous": report["outcomes"].get("ambiguous", 0),
    }
    return report
