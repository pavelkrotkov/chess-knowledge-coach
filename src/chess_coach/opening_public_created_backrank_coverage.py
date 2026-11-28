"""Aggregate source-bound game results and interrupted work."""

import sqlite3
import time

from .opening_public_created_backrank_game import inspect
from .opening_public_mate_coverage import finish, record

COUNTS = ("unknown_observations", "nominated", "positions_unvisited")


def collect(db, rows, binding, move, start, deadline, result):
    for number, row in enumerate(rows):
        try:
            item = inspect(db, row, binding, move, start, deadline)
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
        record(result, {**item, "example": None})
        if item["example"]:
            result["examples"].append({**item["example"], "interrupted": item["interrupted"]})
        for key in COUNTS:
            result[key] += item[key]
        if item["interrupted"]:
            result["unfinished_games"] = len(rows) - number
            result["interrupted"] = True
            finish(result, remaining=len(rows) - number - 1)
            return
