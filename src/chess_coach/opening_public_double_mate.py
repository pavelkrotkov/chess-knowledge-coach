"""Prepare double-check immediate mates for both selected public branches."""

import sqlite3
import time
from functools import partial

from .opening_public_double_mate_game import inspect
from .opening_public_fork_later import branches
from .opening_public_mate_coverage import coverage, finish, record, unavailable
from .opening_public_proof_coverage import _selected
from .opening_public_proof_source import MAX_GAMES


def _collect(db, rows, binding, move, start, deadline, result):
    for number, row in enumerate(rows):
        try:
            item = inspect(db, row, binding, move, start, deadline)
        except (TimeoutError, sqlite3.OperationalError):
            if time.monotonic() < deadline:
                raise
            finish(result, remaining=len(rows) - number)
            return
        except (ValueError, TypeError, KeyError, IndexError):
            result["unsupported"] += 1
            result["preparation_incomplete"] += 1
            continue
        record(result, item)


def branch(db, binding, move, deadline, *, start):
    if binding["control"] == "unknown":
        return unavailable("nominal_context_unknown")
    found = _selected(db, binding, move, deadline)
    if found is None:
        return unavailable("deadline")
    rows, context = found
    selected = rows[:MAX_GAMES]
    result = coverage(context, selected, len(rows) > MAX_GAMES, binding, kind="double_mate")
    _collect(db, selected, binding, move, start, deadline, result)
    return finish(result)


def evaluate(index, identity, start, deadline):
    binding = {**identity, "index_sha256": identity["policy"]["double_mate"]["index_sha256"]}
    result, sample = branches(index, binding, deadline, brancher=partial(branch, start=start))
    return result, sample, None
