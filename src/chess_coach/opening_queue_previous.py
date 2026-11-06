"""Find the newest bounded immutable attempt for a selected source."""

from .opening_queue_artifact import load
from .opening_queue_failure import exists


def finished(directory, item):
    payload = load(directory, item)
    if payload is not None:
        return payload["result"]["status"]
    return "insufficient" if exists(directory, item) else None


def prior(directory, selected):
    for attempt in (2, 1, 0):
        item = {**selected, "attempt": attempt}
        if finished(directory, item):
            return item
    return None
