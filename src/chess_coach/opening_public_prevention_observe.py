"""Account for interrupted and completed per-game prevention work."""

import sqlite3
import time

from .opening_public_prevention_coverage import record, remaining
from .opening_public_prevention_game import classified


class ProofLimit(RuntimeError):
    """The single preparation-wide fork-proof limit was reached."""


def observe(db, selected, binding, move, deadline, start, budget, check, charge, result):
    for number, row in enumerate(selected):
        if budget["exhausted"]:
            remaining(result, len(selected) - number, "proof_limit")
            break
        try:
            found, censored = classified(db, row, binding, move, start, deadline, check, charge)
        except ProofLimit:
            remaining(result, len(selected) - number, "proof_limit")
            break
        except (TimeoutError, sqlite3.OperationalError):
            if time.monotonic() < deadline:
                raise
            remaining(result, len(selected) - number, "deadline")
            break
        record(result, found, censored)
