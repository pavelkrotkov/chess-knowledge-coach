"""Run a separate bounded fork-defense cursor and report."""

from .fork_defense_detector import process_decision
from .fork_worker import process_forks
from .fork_worker_cursor import scan
from .fork_worker_item import process_item

POLICY = "fork-defense-worker-v1"


def process_defenses(db, config):
    return process_forks(db, config, scanner=_scan, processor=_item, policy=POLICY)


def _scan(db, learner, limit):
    return scan(db, learner, limit, namespace="fork-defense-cursor-v1:", policy=POLICY)


def _item(db, position_id, learner, report, outcomes):
    return process_item(db, position_id, learner, report, outcomes, detector=process_decision)
