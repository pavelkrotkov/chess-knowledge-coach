"""Prepare bounded public capture observations from real same-board PVs."""

from .opening_public_capture_pv_game import visit
from .opening_public_capture_pv_position import check
from .opening_public_proof_coverage import _selected
from .opening_public_proof_source import MAX_GAMES


def unavailable():
    return {
        "status": "incomplete",
        "eligible": None,
        "selected": None,
        "entered": 0,
        "analyzed": 0,
        "supported": 0,
        "unsupported": 0,
        "unsupported_positions": 0,
        "censored": 0,
        "unstarted": None,
        "incomplete": None,
        "positions_seen": 0,
        "witness_checked": 0,
        "native_attempted": 0,
        "native_completed": 0,
        "native_qualified": 0,
        "not_requested_positions": 0,
        "not_qualified_positions": 0,
        "attempted_kinds": [],
        "reasons": [],
        "examples": [],
        "records": [],
    }


def branch(connection, binding, move, engine, deadline):
    result = unavailable()
    if binding["control"] == "unknown":
        result["reasons"].append("nominal_context_unknown")
        return result
    check(deadline)
    found = _selected(connection, binding, move, deadline)
    if found is None:
        return result
    rows, context = found
    selected = rows[:MAX_GAMES]
    result["eligible"] = context["matched_candidates"]
    result["selected"] = len(selected)
    for row in selected:
        if not visit(connection, row, binding, move, engine, deadline, result):
            break
    result["unstarted"] = len(selected) - result["entered"]
    result["incomplete"] = len(selected) - result["analyzed"]
    result["not_requested_positions"] = result["positions_seen"] - result["native_attempted"]
    result["not_qualified_positions"] = result["positions_seen"] - result["native_qualified"]
    if result["incomplete"] == 0:
        result["status"] = "prepared"
    return result
