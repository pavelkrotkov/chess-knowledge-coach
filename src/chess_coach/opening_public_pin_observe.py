"""Collect completed pin game inspections under shared proof limits."""

import sqlite3
import time

from .opening_public_pin_coverage import record
from .opening_public_pin_game import inspect
from .opening_public_prevention_observe import ProofLimit


def observe(db, selected, binding, move, deadline, result, check, charge):
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
            result["preparation_incomplete"] += 1
            continue
        record(result, item, censored)
    else:
        return
    result["preparation_incomplete"] += remaining
