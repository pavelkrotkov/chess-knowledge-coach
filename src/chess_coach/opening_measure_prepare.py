"""Prepare a source-bound opening comparison and publish it privately."""

import os
import time

from .deep_execution_lock import deep_lock
from .fact_fingerprint import canonical, digest
from .opening_measure_engine import measure
from .opening_measure_source import selection
from .purpose_config import WORKER_SECONDS, configuration
from .tactical_course_budget import Budget
from .tactical_course_publish import publish


def _config(db, game_id, engine):
    binary, config = configuration(db, game_id, engine)
    config = dict(config)
    config.pop("scout_nodes")
    config.pop("scout_seconds")
    config.update(
        {
            "purpose": "opening-catalog-comparison",
            "purpose_policy": "opening-catalog-comparison-v1",
            "candidate_set": "played-and-selected-catalog",
        }
    )
    return binary, config


def _prepare(db, game_id, position_id, alternative, output, engine):
    budget = Budget(db)
    deadline = time.monotonic() + WORKER_SECONDS
    budget.expires = min(budget.expires, deadline)
    with deep_lock(db.path):
        with budget.scope(snapshot=False):
            binding, owned = selection(
                db, game_id, position_id, os.environ["CHESS_SUBJECT"], alternative
            )
        with budget.scope(snapshot=False):
            binary, config = _config(db, game_id, engine)
        result = measure(binary, config, owned["board"], owned["position"], alternative, deadline)
        with budget.scope(snapshot=False):
            _, after = _config(db, game_id, engine)
            if after != config or time.monotonic() >= deadline:
                raise ValueError("configuration or deadline changed")
        payload = {
            "version": "opening-catalog-measurement-v1",
            "source": binding,
            "configuration": config,
            "result": result,
            "interpretation": "Selected roots only; no global best, opening fit or soundness claim.",
        }
        envelope = {"sha256": digest(canonical(payload)), "measurement": payload}
        publish(output, envelope, budget, readonly=True)
