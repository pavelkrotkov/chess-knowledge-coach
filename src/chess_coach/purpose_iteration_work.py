"""Retain maxima across all updates in one shared search."""

from .deep_execution_work import _valid


def update(work, info):
    for key in work:
        value = info.get(key)
        if _valid(value, key != "time"):
            previous = work[key]
            work[key] = value if previous is None else max(previous, value)
