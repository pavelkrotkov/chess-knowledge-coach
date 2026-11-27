"""Scan a public game and account for partial capture observations."""

import sqlite3
import time

from .opening_public_capture_pv_position import check, observe
from .opening_public_capture_pv_record import record
from .opening_public_defense_pv_position import observe as defense_observe
from .opening_public_proof_history import positions

MAX_SEARCHES = 2


def _scan_game(connection, row, binding, move, engine, deadline, result, nomination):
    rows, candidates, censored, safe = positions(
        connection, row[0], row[1], binding, move, deadline, all_moves=True
    )
    result["censored"] += int(censored)
    result["positions_seen"] += len(candidates)
    if not safe:
        result["unsupported_positions"] += len(candidates)
        return False
    completed_before = result["native_completed"]
    for ply, board, recorded in candidates:
        check(deadline)
        defense = "defense_pv" in binding["policy"]
        kind = nomination(board, recorded, deadline, result, defense)
        if kind is None:
            continue
        observer = defense_observe if defense else observe
        result["attempted_kinds"].append(kind)
        result["native_attempted"] += 1
        measured = observer(board, recorded, engine, deadline)
        record(connection, row, binding, rows, ply, board, recorded, measured, result)
        if engine["failed"]:
            return False
        if len(result["attempted_kinds"]) == MAX_SEARCHES:
            break
    # An ambiguous returned search still counts as searched; every position must return.
    return result["native_completed"] - completed_before == len(candidates)


def visit(connection, row, binding, move, engine, deadline, result, nomination):
    if (
        engine["failed"]
        or len(result["attempted_kinds"]) == MAX_SEARCHES
        or time.monotonic() >= deadline
    ):
        return False
    result["entered"] += 1
    before = len(result["examples"])
    unsupported = result["unsupported_positions"]
    complete = False
    # Earlier positives survive a later deadline or unsupported position.
    try:
        complete = _scan_game(connection, row, binding, move, engine, deadline, result, nomination)
    except TimeoutError:
        return False
    except sqlite3.OperationalError:
        if time.monotonic() < deadline:
            raise
        return False
    except (ValueError, TypeError, KeyError, IndexError):
        result["unsupported_positions"] += 1
    finally:
        result["supported"] += int(len(result["examples"]) > before)
        result["unsupported"] += int(result["unsupported_positions"] > unsupported)
        result["analyzed"] += int(complete)
    return True
