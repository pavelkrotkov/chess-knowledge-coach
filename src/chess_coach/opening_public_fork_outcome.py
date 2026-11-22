"""Count scoped fork roots without labeling unknown positions as geometry."""

from typing import cast


def record(result, state, example):
    if state == "scope":
        result["unsupported"] += 1
        return
    result["geometries"] += 1
    result[state] = cast(int, result[state]) + 1
    if result["example"] is None and example is not None:
        result["example"] = example
