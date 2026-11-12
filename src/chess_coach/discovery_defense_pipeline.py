"""Publish and rotate source-owned discovered-mate defense observations."""

from dataclasses import replace
from functools import partial

from .discovery_defense_contract import FACT, MAPPER, PRODUCER, SCOPE, VERSION
from .discovery_defense_observation import observe
from .fork_publish import publish
from .fork_replay import current_result
from .fork_storage import fact_run
from .fork_worker import process_forks
from .fork_worker_cursor import scan
from .fork_worker_item import process_item
from .mapping_runs import record_mapping_run_in_transaction
from .material_source import prepare
from .material_source_marker import source_marker

POLICY = "discovery-mate-defense-worker-v1"


def process_decision(db, position_id, learner):
    if db.connection.in_transaction:
        raise RuntimeError("discovery defense detection requires an idle database")
    source = prepare(db, position_id, learner)
    replay = current_result(
        db, source, producer=PRODUCER, mapper=MAPPER, version=VERSION, fact_type=FACT
    )
    if replay is not None:
        if source_marker(db, position_id, source["game_id"], learner) != source["source_marker"]:
            raise ValueError("discovery defense source changed")
        return replay
    fact = observe(
        source["board"], source["context"]["played_move"], source["best"], source["played"]
    )
    writer = partial(fact_run, producer=PRODUCER, version=VERSION, fact_type=FACT)
    return publish(db, source, fact, fact_writer=writer, mapping_writer=_mapping)


def _mapping(db, source, inputs, run, fact):
    if fact is None:
        return None
    context = source["context"]
    details = {
        "observation": fact,
        "provenance": source["provenance"],
        "qualification": "Provisional bounded observation. Mastery and intent remain unknown.",
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
        position_id=source["position_id"],
        producer=MAPPER,
        mapper_version=VERSION,
        subject=context["subject"],
        operation="prevent",
        scope_key=SCOPE,
        input_data={"source": inputs, "fact_run": run["run_id"], "context": details},
        mappings=[item],
    )


def process_defenses(db, config):
    scanner = partial(scan, namespace="discovery-mate-defense-cursor-v1:", policy=POLICY)
    processor = partial(process_item, detector=process_decision)
    limited = replace(
        config,
        material_max_scan=min(config.material_max_scan, 20),
        material_max_decisions=min(config.material_max_decisions, 4),
    )
    return process_forks(db, limited, scanner=scanner, processor=processor, policy=POLICY)
