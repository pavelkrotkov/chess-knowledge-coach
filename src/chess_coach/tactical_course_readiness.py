"""Retain only validated aggregate diagnostics for an empty course."""

from .tactical_course_selection import PER_PAIR
from .tactical_export_coverage import coverage
from .tactical_export_gaps import OWN, OWN_DEFERRED, omissions


def _coverage(rows, chosen):
    coverage(rows, chosen)
    return [
        {
            "skill": row["skill"],
            "operation": row["operation"],
            "status": row["status"],
            "examined": row["examined"],
            "limited": row["limited"],
            "excluded": {},
        }
        for row in rows
    ]


def _omissions(items, rows, chosen):
    if not isinstance(items, list) or len(items) > len(chosen) * PER_PAIR:
        raise ValueError("invalid readiness omissions")
    result = {}
    for item in items:
        pair = (item["skill"], item["operation"])
        reason = item["reason"]
        _add(result, pair, reason)
    clean = [
        {"skill": skill, "operation": operation, "reason": result[(skill, operation)]}
        for skill, operation in chosen
        if (skill, operation) in result
    ]
    if len(clean) != len(result):
        raise ValueError("invalid readiness pair")
    omissions(
        {"coverage": rows, "unavailable": clean}, pairs=chosen, modern=True, owned_deadline=True
    )
    return clean


def _add(result, pair, reason):
    if reason not in {OWN, OWN_DEFERRED}:
        raise ValueError("invalid empty-course omission")
    result[pair] = OWN_DEFERRED if pair in result and result[pair] != reason else reason


def selection(rows, unavailable, chosen):
    clean = _coverage(rows, chosen)
    return {"coverage": clean, "unavailable": _omissions(unavailable, clean, chosen)}
