"""Resolve the single slot and bounded retries without repeating completed work."""

from .opening_queue_previous import finished, prior


def choose(directory, selected, old, retry):
    if old is not None:
        outcome = finished(directory, old)
        if old["state"] == "unavailable" and outcome is None:
            raise ValueError("comparison failure receipt unavailable")
        if old["id"] == selected["id"]:
            return _same(selected, old, retry, outcome)
        if not outcome:
            raise ValueError("another comparison is queued")
    return _earlier(directory, selected, retry)


def _same(selected, old, retry, outcome):
    if retry and outcome == "insufficient":
        return _next(selected, old)
    return old


def _earlier(directory, selected, retry):
    previous = prior(directory, selected)
    if retry and previous and finished(directory, previous) == "insufficient":
        return _next(selected, previous)
    return previous or selected


def _next(selected, prior):
    if prior["attempt"] >= 2:
        raise ValueError("comparison retry limit reached")
    return {**selected, "attempt": prior["attempt"] + 1}
