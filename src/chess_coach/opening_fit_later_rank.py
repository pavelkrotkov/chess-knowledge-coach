"""Apply the existing attainable-coverage gap to a later branch."""

from .opening_fit_rank import MIN_GAP, MIN_PUBLIC, bounds


def _interval(value):
    if value["unknown_control"] or value["matched_control"] < MIN_PUBLIC:
        return None
    return bounds({"profile": {"center": {"valid": value["valid"]}}}, value)


def _eligible(owned, move, control):
    return owned.get(move, {}).get("positive") and owned[move]["time_control"] == control


def _winner(moves, owned, intervals, control):
    for move in moves:
        other = next(item for item in moves if item != move)
        if _eligible(owned, move, control) and intervals[move][0] - intervals[other][1] >= MIN_GAP:
            return move
    return None


def rank(moves, owned, public, control):
    if control == "unknown":
        return None
    intervals = {move: _interval(public[move]) for move in moves}
    if any(value is None for value in intervals.values()):
        return None
    return _winner(moves, owned, intervals, control)
