"""Prepare recorded material discoveries on both selected public branches."""

import sqlite3
import time

from .opening_public_discovery_material_game import inspect
from .opening_public_mate_coverage import coverage, finish, record, unavailable
from .opening_public_proof_coverage import _selected
from .opening_public_proof_source import MAX_GAMES

COUNTS = ("roots_checked", "geometry_unresolved", "positions_unvisited")


def _collect(db, rows, binding, move, deadline, result):
    for number, row in enumerate(rows):
        try:
            item = inspect(db, row, binding, move, deadline)
        except (TimeoutError, sqlite3.OperationalError):
            if time.monotonic() < deadline:
                raise
            result["unfinished_games"] = len(rows) - number
            finish(result, remaining=result["unfinished_games"])
            return
        except (ValueError, TypeError, KeyError, IndexError):
            result["unsupported"] += 1
            result["preparation_incomplete"] += 1
            continue
        record(result, item)
        for key in COUNTS:
            result[key] += item[key]


def branch(db, binding, move, deadline):
    if binding["control"] == "unknown":
        return unavailable("nominal_context_unknown")
    found = _selected(db, binding, move, deadline)
    if found is None:
        return unavailable("deadline")
    rows, context = found
    selected = rows[:MAX_GAMES]
    result = coverage(context, selected, len(rows) > MAX_GAMES, binding, kind="discovery_material")
    result.update(dict.fromkeys((*COUNTS, "unfinished_games"), 0))
    result["counts_scope"] = "completed_game_inspections"
    _collect(db, selected, binding, move, deadline, result)
    return finish(result)
