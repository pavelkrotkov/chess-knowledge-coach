"""Aggregate bounded recorded and partial opportunity game inspections."""

import sqlite3
import time

from .opening_public_discovery_material_game import inspect
from .opening_public_discovery_opportunity import record_opportunity
from .opening_public_mate_coverage import finish, record

COUNTS = ("roots_checked", "geometry_unresolved", "positions_unvisited")


def collect(db, rows, binding, move, deadline, result):
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
        if "discovery_opportunity" in binding["policy"]:
            record_opportunity(result, item)
        else:
            record(result, item)
        for key in COUNTS:
            result[key] += item[key]
        if item.get("interrupted"):
            result["unfinished_games"] = len(rows) - number
            result["interrupted"] = True
            finish(result, remaining=len(rows) - number - 1)
            return
