"""Validate a generator's complete permutation of approved examples."""

import json


def _permutation(order, count):
    return (
        isinstance(order, list)
        and all(type(i) is int for i in order)
        and sorted(order) == list(range(count))
    )


def order(response, count):
    if not isinstance(response, str) or len(response) > 4096:
        return None
    try:
        value = json.loads(response)
        if not isinstance(value, dict) or set(value) != {"order"}:
            return None
        return value["order"] if _permutation(value["order"], count) else None
    except (ValueError, TypeError):
        return None
