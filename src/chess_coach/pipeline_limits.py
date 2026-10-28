"""Validate explicit resource budgets and stage versions."""

import math

from .pipeline_versions import validate_versions


def validate_integer_limits(config) -> None:
    limits = (
        (config.max_games, 1, 100),
        (config.max_scan, 1, 10000),
        (config.max_positions, 1, 1000),
        (config.nodes, 1, 10000000),
        (config.threads, 1, 8),
        (config.hash_mb, 1, 1024),
        (config.page_size, 1, 999),
        (config.network_retries, 0, 3),
        (config.network_requests, 1, 100),
        (config.network_bytes, 1, 33554432),
    )
    if any(type(value) is not int or not low <= value <= high for value, low, high in limits):
        raise ValueError("invalid pipeline resource budget")


def validate_other_limits(config) -> None:
    limits = (
        (config.seconds_per_position, 0, 10),
        (config.network_timeout, 0, 60),
        (config.network_seconds, 0, 1800),
        (config.network_sleep, 0, 300),
    )
    if any(_invalid_time(v, low, high) for v, low, high in limits):
        raise ValueError("invalid pipeline time budget")
    if (
        config.seconds_per_position == 0
        or config.network_timeout == 0
        or config.network_seconds == 0
    ):
        raise ValueError("time limits must be positive")
    validate_versions(config)


def _invalid_time(value, low, high) -> bool:
    return (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not low <= value <= high
    )
