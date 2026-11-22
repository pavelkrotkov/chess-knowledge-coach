"""Prepare a source-bound opening comparison and publish it privately."""

import json
import os
import time

from .deep_execution_lock import deep_lock
from .fact_fingerprint import canonical, digest
from .opening_measure_engine import measure
from .opening_measure_source import selection
from .opening_queue_binding import V1, V2, _config
from .opening_queue_files import MAX_BYTES
from .purpose_config import WORKER_SECONDS
from .tactical_course_budget import Budget
from .tactical_course_publish import publish


def _prepare(db, game_id, position_id, alternative, output, engine, *, learner=None, expected=None):
    budget = Budget(db)
    deadline = time.monotonic() + WORKER_SECONDS
    budget.expires = min(budget.expires, deadline)
    policy = expected[1].get("purpose_policy", V1) if expected is not None else V2
    with deep_lock(db.path):
        with budget.scope(snapshot=False):
            binding, owned = selection(
                db, game_id, position_id, learner or os.environ["CHESS_SUBJECT"], alternative
            )
        with budget.scope(snapshot=False):
            binary, config = _config(db, game_id, engine, owned["board"], policy)
            if expected is not None and (binding, config) != expected:
                raise ValueError("queued source or configuration changed")
        result = measure(binary, config, owned["board"], owned["position"], alternative, deadline)
        with budget.scope(snapshot=False):
            _, after = _config(db, game_id, engine, owned["board"], policy)
            if after != config or time.monotonic() >= deadline:
                raise ValueError("configuration or deadline changed")
        envelope = _envelope(binding, config, result)
        publish(output, envelope, budget, readonly=True)
        return envelope["measurement"]


def _payload(binding, config, result):
    # Old queued work keeps its exact v1 envelope and interpretation.
    if config.get("purpose_policy") == V2:
        version = "opening-catalog-measurement-v2"
        interpretation = (
            "All legal roots at one bounded search depth; no opening fit or soundness claim."
        )
    else:
        version = "opening-catalog-measurement-v1"
        interpretation = "Selected roots only; no global best, opening fit or soundness claim."
    return {
        "version": version,
        "source": binding,
        "configuration": config,
        "result": result,
        "interpretation": interpretation,
    }


def _envelope(binding, config, result):
    payload = _payload(binding, config, result)
    envelope = {"sha256": digest(canonical(payload)), "measurement": payload}
    if config.get("purpose_policy") == V2:
        encoded = json.dumps(envelope, sort_keys=True, allow_nan=False).encode()
        if len(encoded) > MAX_BYTES:
            payload = _payload(
                binding, config, {"status": "insufficient", "reason": "result_exceeds_limit"}
            )
            envelope = {"sha256": digest(canonical(payload)), "measurement": payload}
            if len(json.dumps(envelope, sort_keys=True, allow_nan=False).encode()) > MAX_BYTES:
                raise ValueError("opening measurement exceeds limit")
    return envelope
