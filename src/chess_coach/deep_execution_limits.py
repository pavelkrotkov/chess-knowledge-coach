"""Validate independent deep search and invocation budgets."""

import math


def validate_options(options):
    limits = (
        (options.nodes, 1, 10000000),
        (options.multipv, 1, 3),
        (options.threads, 1, 4),
        (options.hash_mb, 1, 256),
        (options.min_depth, 1, 100),
        (options.max_jobs, 1, 100),
    )
    if any(type(value) is not int or not low <= value <= high for value, low, high in limits):
        raise ValueError("invalid deep-analysis integer limit")
    _validate_time(options.seconds)
    if type(options.retry_insufficient) is not bool:
        raise ValueError("invalid retry option")


def _validate_time(seconds):
    if (
        isinstance(seconds, bool)
        or not isinstance(seconds, (int, float))
        or not math.isfinite(seconds)
        or not 0 < seconds <= 10
    ):
        raise ValueError("invalid deep-analysis time limit")
