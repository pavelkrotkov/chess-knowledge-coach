"""Account for bounded public-game coverage of one selected branch."""

import sqlite3
import time

from .opening_profile_queen_replay import _end
from .opening_public_fork_coverage import failed, finish, record
from .opening_public_fork_coverage import start as start_fork
from .opening_public_proof_replay import replay
from .opening_public_proof_source import MAX_GAMES
from .opening_recent_select import rows as select_rows


def unavailable():
    return {
        "status": "incomplete",
        "eligible": None,
        "selected": None,
        "analyzed": None,
        "unsupported": None,
        "supported": None,
        "interrupted": True,
        "censored": None,
        "preparation_incomplete": None,
        "example": None,
    }


# An analyzed game can also contain unsupported captures; these counts overlap.
# A frontier or cutoff says nothing about demands beyond the recorded window.
def _inspect(connection, row, binding, move, start, deadline, result, fork_budget):
    try:
        result["censored"] += int(_end(binding["ply"], row[1])[1] != "ended")
        observed = replay(connection, row, binding, move, start, deadline, fork_budget=fork_budget)
    except TimeoutError:
        return False
    except sqlite3.OperationalError:
        if time.monotonic() < deadline:
            raise
        return False
    except (ValueError, TypeError, KeyError, IndexError):
        result["unsupported"] += 1
        reasons = result["unsupported_reasons"]
        reasons["history_unavailable"] = reasons.get("history_unavailable", 0) + 1
        failed(result, fork_budget)
        return True
    result["analyzed"] += 1
    result["unsupported"] += int(bool(observed["unsupported"]))
    result["supported"] += int(observed["example"] is not None)
    for reason in observed["unsupported"]:
        reasons = result["unsupported_reasons"]
        reasons[reason] = reasons.get(reason, 0) + 1
    record(result, fork_budget, observed["fork"])
    if result["example"] is None:
        result["example"] = observed["example"]
    return True


def _selected(connection, binding, move, deadline):
    try:
        result = select_rows(
            connection, binding["source"]["parent"], move, binding["ply"], binding["control"]
        )
    except sqlite3.OperationalError:
        if time.monotonic() >= deadline:
            return None
        raise
    return None if time.monotonic() >= deadline else result


# Unknown context is unavailable, not an empty sample or a negative result.
def branch(connection, binding, move, start, deadline):
    if binding["control"] == "unknown":
        return {**unavailable(), "interrupted": False, "reason": "nominal_context_unknown"}
    found = _selected(connection, binding, move, deadline)
    if found is None:
        return unavailable()
    rows, context = found
    selected = rows[:MAX_GAMES]
    result = {
        "status": "prepared",
        "eligible": context["matched_candidates"],
        "excluded_context": context["excluded_context"],
        "unknown_context": context["unknown_context"],
        "selected": len(selected),
        "analyzed": 0,
        "unsupported": 0,
        "supported": 0,
        "interrupted": False,
        "censored": 0,
        "preparation_incomplete": 0,
        "example": None,
        "more_eligible": len(rows) > MAX_GAMES,
        "unsupported_reasons": {},
    }
    fork_budget = start_fork(binding, result, len(selected))
    for row in selected:
        if not _inspect(connection, row, binding, move, start, deadline, result, fork_budget):
            result["interrupted"] = True
            break
    finish(result, fork_budget, len(selected))
    result["preparation_incomplete"] = len(selected) - result["analyzed"]
    if result["preparation_incomplete"] or result["interrupted"]:
        result["status"] = "incomplete"
    return result
