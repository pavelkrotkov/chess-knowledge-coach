"""Compare only ordered, disjoint current first-encounter samples."""

import chess

from .mate_assessment_compare import SAMPLE, comparable


def _sample(items):
    return {
        "items": items,
        "size": len(items),
        "correct": sum(item["status"] == "correct" for item in items),
        "start": items[0]["started_at"],
        "end": items[-1]["started_at"],
    }


def _reason(items, limited):
    if not comparable(items, limited):
        return "Two ordered samples of 10 current unassisted first checks are needed."
    if len({item["started_at"] for item in items}) != len(items):
        return "Some check start times are tied."
    earlier, later = items[:SAMPLE], items[-SAMPLE:]
    if max(item["answered_at"] for item in earlier) >= min(item["started_at"] for item in later):
        return "The assessment intervals overlap."
    return None


def group(scope, items, limited):
    _, _, side, mover, target, mechanism, rating, deviation = scope
    reason = (
        "Difficulty uncertainty was not recorded." if deviation is None else _reason(items, limited)
    )
    result = {
        "side": side,
        "mover": chess.piece_name(mover),
        "target": chess.piece_name(target),
        "mechanism": mechanism,
        "rating": rating * 200,
        "deviation": None if deviation is None else deviation * 100,
        "count": len(items),
        "reason": reason,
    }
    if reason:
        return result
    first, last = _sample(items[:SAMPLE]), _sample(items[-SAMPLE:])
    a, b = first["correct"], last["correct"]
    return {
        **result,
        "earlier": first,
        "later": last,
        "direction": "more" if b > a else "fewer" if b < a else "equal",
    }
