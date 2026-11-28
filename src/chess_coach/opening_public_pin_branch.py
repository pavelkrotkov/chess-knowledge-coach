"""Select and count public pin observations for one indexed branch."""

import sqlite3
import time

from .opening_public_pin_coverage import empty, record
from .opening_public_pin_game import inspect
from .opening_public_prevention_observe import ProofLimit
from .opening_public_proof_coverage import _selected
from .opening_public_proof_source import MAX_GAMES


def _observe(db, selected, binding, move, deadline, result, check, charge):
    for index, row in enumerate(selected):
        remaining = len(selected) - index
        try:
            item, censored = inspect(db, row, binding, move, deadline, check, charge)
        except ProofLimit:
            result["proof_limit"] = True
            break
        except (TimeoutError, sqlite3.OperationalError):
            if time.monotonic() < deadline:
                raise
            result["interrupted"] = True
            break
        except (ValueError, TypeError, KeyError, IndexError):
            result["unsupported"] += 1
            continue
        record(result, item, censored)
    else:
        return
    result["preparation_incomplete"] += remaining


def branch(db, binding, move, deadline, *, budget, check):
    if binding["control"] == "unknown":
        return {
            "status": "incomplete",
            "reason": "nominal_context_unknown",
            "eligible": None,
            "selected": None,
        }
    found = _selected(db, binding, move, deadline)
    if found is None:
        return {"status": "incomplete", "reason": "deadline", "eligible": None, "selected": None}
    rows, context = found
    selected = rows[:MAX_GAMES]
    result = empty(context, len(selected), len(rows) > MAX_GAMES)
    budget["branch"] = 0

    def charge():
        check()
        policy = binding["policy"]["pin"]
        if (
            budget["branch"] >= policy["proofs_per_branch"]
            or budget["total"] >= policy["proofs_per_preparation"]
        ):
            raise ProofLimit()
        budget["branch"] += 1
        budget["total"] += 1

    _observe(db, selected, binding, move, deadline, result, check, charge)
    result["proofs"] = budget["branch"]
    if result["preparation_incomplete"] or result["interrupted"]:
        result["status"] = "incomplete"
    return result
