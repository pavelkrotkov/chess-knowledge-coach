"""Validate independent automatic deep budgets without altering cheap scans."""

from .deep_execution_config import DeepOptions
from .deep_execution_limits import validate_options


def validate_deep_config(config):
    limits = (
        (config.deep_max_scan, 1, 10000),
        (config.deep_max_games, 1, 100),
        (config.deep_per_game, 1, 100),
        (config.deep_max_jobs, 1, 100),
    )
    if type(config.deep_enabled) is not bool or any(
        type(value) is not int or not low <= value <= high for value, low, high in limits
    ):
        raise ValueError("invalid automatic deep budget")


def deep_options(config, *, max_jobs=None):
    options = DeepOptions(
        engine_path=config.engine_path,
        nodes=config.deep_nodes,
        seconds=config.deep_seconds,
        multipv=config.deep_multipv,
        threads=1,
        hash_mb=min(config.hash_mb, 256),
        max_jobs=config.deep_max_jobs if max_jobs is None else max_jobs,
    )
    validate_options(options)
    return options


def public_limits(config):
    return {
        "enabled": config.deep_enabled,
        "scan_games": config.deep_max_scan,
        "selection_games": config.deep_max_games,
        "per_game": config.deep_per_game,
        "jobs": config.deep_max_jobs,
        "nodes_per_search": config.deep_nodes,
        "seconds_per_search": config.deep_seconds,
        "multipv": config.deep_multipv,
        "threads": 1,
    }


def combined_status(status, deep):
    if status == "complete" and deep["status"] == "partial":
        return "partial"
    return status
