"""Run a single engine with bounded cleanup and source configuration."""

import time

from .deep_execution_engine import start_engine, stop_engine
from .purpose_config import configuration
from .purpose_search import search


def execute(db, snapshot, config, deadline):
    if snapshot["board"].legal_moves.count() < 2:
        return "insufficient", "forced_move", {}
    binary, fresh = configuration(db, snapshot["game_id"], config["engine_path"])
    if fresh != config:
        return "insufficient", "engine_configuration_changed", {}
    if time.monotonic() >= deadline:
        return "insufficient", "worker_deadline", {}
    runtime_config = dict(config)
    engine, metadata = start_engine(binary, runtime_config)
    try:
        result, issue = search(engine, snapshot["board"], snapshot["position"], deadline)
        result["engine"] = dict(metadata.id)
        result["runtime_engine"] = {
            key: runtime_config.get(key)
            for key in ("engine_id", "nnue_options", "native_wdl_requested")
        }
        result["scope"] = "played-and-scout-nominee"
    finally:
        stopped = stop_engine(engine)
    if not stopped:
        return "insufficient", "engine_shutdown_failed", result
    if not unchanged(db, snapshot["game_id"], config):
        return "insufficient", "engine_configuration_changed", result
    return ("insufficient", issue, result) if issue else ("complete", "comparable", result)


def unchanged(db, game_id, config):
    try:
        _, after = configuration(db, game_id, config["engine_path"])
    except (RuntimeError, OSError, ValueError):
        return False
    return after == config
