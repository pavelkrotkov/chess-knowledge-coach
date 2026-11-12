"""Publish and rotate source-owned discovered-mate defense observations."""

from collections import Counter
from dataclasses import replace
from functools import partial

from .discovery_mate_prevent_source import process_source
from .discovery_prevent_worker_item import combined
from .fork_worker import process_forks
from .fork_worker_cursor import scan
from .fork_worker_item import process_item
from .material_source import prepare

POLICY = "discovery-mate-defense-worker-v1"


def process_decision(db, position_id, learner):
    if db.connection.in_transaction:
        raise RuntimeError("discovery defense detection requires an idle database")
    source = prepare(db, position_id, learner)
    return process_source(db, source)


def process_defenses(db, config):
    scanner = partial(scan, namespace="discovery-mate-defense-cursor-v1:", policy=POLICY)
    exclusions = Counter()
    processor = partial(process_item, detector=partial(combined, exclusions=exclusions))
    limited = replace(
        config,
        material_max_scan=min(config.material_max_scan, 20),
        material_max_decisions=min(config.material_max_decisions, 4),
    )
    result = process_forks(db, limited, scanner=scanner, processor=processor, policy=POLICY)
    result["material_unresolved"] = dict(sorted(exclusions.items()))
    return result
