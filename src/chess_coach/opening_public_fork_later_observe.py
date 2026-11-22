"""Account for bounded per-game continuation observations."""

import sqlite3
import time

from .opening_public_fork_later_replay import inspect
from .opening_public_fork_stats import add


def observe(db, selected, binding, move, deadline, result):
    budget = {"proofs": 0}
    for row in selected:
        try:
            item, censored = inspect(db, row, binding, move, budget, deadline)
        except (TimeoutError, sqlite3.OperationalError):
            if time.monotonic() < deadline:
                raise
            result["interrupted"] = True
            break
        except (ValueError, TypeError, KeyError, IndexError):
            result["attempted"] += 1
            result["unsupported"] += 1
            continue
        result["censored"] += int(censored)
        if item is None:
            result["attempted"] += 1
            result["ended_before_window"] += 1
        else:
            add(result, item)
    result["incomplete"] += len(selected) - result["attempted"]
    result["proofs"] = budget["proofs"]
