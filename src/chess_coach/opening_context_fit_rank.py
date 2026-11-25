"""Conservatively compare qualified first-turn opportunity intervals."""

from .opening_fit_later_rank import _interval
from .opening_fit_rank import MIN_GAP


def result(items, public):
    intervals = {item["uci"]: _interval(public[item["uci"]]) for item in items}
    if any(value is None for value in intervals.values()):
        return {"status": "withheld", "reason": "public_opportunities_insufficient"}
    moves = list(intervals)
    for move in moves:
        other = next(value for value in moves if value != move)
        if intervals[move][0] - intervals[other][1] >= MIN_GAP:
            return {"status": "supported", "reason": "conservative_separation", "winner": move}
    return {"status": "tie", "reason": "no_conservative_separation"}
