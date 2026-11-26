"""Retain bounded exact-root detail from the existing capture scan."""

from .capture_game_root_validate import record, section
from .short_mate_trend_turns import inspect as inspect_turns


def _attach(state, item, rows, details, expected):
    for row, detail, original in zip(rows, details, expected, strict=False):
        if detail and row == original:
            record(state, item, row, detail)


def inspect(db, learner, item, deadline, quota, *, state, classifier, seconds):
    current = section(state, item)
    if current is None:
        return 0
    collected = []

    def classify(board, played, until, clock):
        detail = {}
        result = classifier(board, played, until, clock, details=detail)
        collected.append(detail)
        return result

    first = len(item["results"])
    cursor = current.get("next", 0)
    shadow = first == item["eligible"] and cursor < first
    if first == item["eligible"] and cursor == first:
        return 0
    target = {**item, "results": item["results"][:cursor]} if shadow else item
    start = len(target["results"])
    used = inspect_turns(db, learner, target, deadline, quota, classifier=classify, seconds=seconds)
    rows = target["results"][start:]
    expected = item["results"][start:] if shadow else rows
    _attach(state, item, rows, collected, expected)
    if shadow or cursor == first:
        item["root_details"]["next"] = start + used
    return used
