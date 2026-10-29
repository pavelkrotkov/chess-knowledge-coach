"""Record actual search work without summing shared MultiPV observations."""

import math


def shared_work(lines):
    nodes = _maximum(lines, "nodes", integer=True)
    depth = _maximum(lines, "depth", integer=True)
    seconds = _maximum(lines, "time", integer=False)
    return {"nodes": nodes, "depth": depth, "time_seconds": seconds, "shared_search": True}


def _maximum(lines, key, *, integer):
    values = []
    for line in lines:
        value = line.get(key)
        if _valid(value, integer):
            values.append(value)
    return max(values) if values else None


def _valid(value, integer):
    if type(value) not in (int, float) or (integer and type(value) is not int):
        return False
    return math.isfinite(value) and value >= 0
