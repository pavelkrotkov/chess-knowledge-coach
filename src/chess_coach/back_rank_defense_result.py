"""Classify bounded defensive choices using witnessed legal anchors."""

from .back_rank_defense_choices import anchors


def classify(result, candidates):
    items = result["alternatives"]
    played = next(item for item in items if item["move"]["uci"] == result["played"])
    witnesses = anchors(items, candidates)
    if played.get("back_rank"):
        return _allows(result, played, candidates, witnesses)
    if _avoids(played, witnesses):
        return {
            **result,
            "status": "opportunity",
            "outcome": "avoids",
            "origin": "anchored_preexisting",
            "anchors": witnesses,
        }
    reason = "other_immediate_mate" if played.get("other_mates") else "no_anchored_comparison"
    return {**result, "status": "unknown", "reason": reason, "anchors": witnesses}


def _allows(result, played, candidates, witnesses):
    matches = any(mate["move"]["uci"] in (candidates or set()) for mate in played["back_rank"])
    origin = _origin(candidates, matches, witnesses)
    return {
        **result,
        "status": "opportunity",
        "outcome": "allows",
        "origin": origin,
        "anchors": witnesses,
    }


def _origin(candidates, matches, witnesses):
    if candidates is None:
        return "unresolved"
    if not matches:
        return "newly_allowed"
    return "anchored_preexisting" if witnesses else "unverified_preexisting"


def _avoids(played, witnesses):
    return played["status"] == "complete" and not played["other_mates"] and bool(witnesses)
