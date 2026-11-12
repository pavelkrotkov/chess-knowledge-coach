"""Publish and rotate source-owned discovered-mate defense observations."""

from collections import Counter
from functools import partial

from .discovery_defense_archive import POLICY as POLICY
from .discovery_defense_report import summarize
from .discovery_defense_schedule import run
from .discovery_mate_prevent_source import process_source
from .discovery_prevent_worker_item import combined
from .fork_worker_item import process_item
from .material_source import prepare
from .pipeline_inputs import engine_identity


def process_decision(db, position_id, learner):
    if db.connection.in_transaction:
        raise RuntimeError("discovery defense detection requires an idle database")
    source = prepare(db, position_id, learner)
    return process_source(db, source)


def _lane():
    return {
        "examined": 0,
        "processed": 0,
        "replayed": 0,
        "unavailable": 0,
        "capped": False,
        "outcomes": Counter(),
        "material_unresolved": Counter(),
        "success_coverage": Counter(),
        "games_examined": 0,
        "source_unavailable": 0,
        "overlap": 0,
        "scanned": False,
    }


def _attempt(db, learner, lane):
    detector = partial(
        combined, exclusions=lane["material_unresolved"], successes=lane["success_coverage"]
    )
    processor = partial(process_item, detector=detector)
    return lambda position: processor(db, position, learner, lane, lane["outcomes"])


def process_defenses(db, config, engine_hash=None):
    limits = {
        "positions": min(config.material_max_scan, 20),
        "decisions": min(config.material_max_decisions, 4),
    }
    lanes = {"recent": _lane(), "archive": _lane()}
    attempts = {name: _attempt(db, config.learner, lane) for name, lane in lanes.items()}
    engine_hash = engine_hash if engine_hash is not None else engine_identity(config.engine_path)
    run(db, config, engine_hash, lanes, attempts, limits)
    return summarize(lanes, limits)
