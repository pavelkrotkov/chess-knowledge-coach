"""Scan a public game and account for partial capture observations."""

import sqlite3
import time

from .opening_public_capture_pv_position import candidate, check, observe
from .opening_public_capture_pv_record import record
from .opening_public_proof_history import positions

MAX_SEARCHES = 2


def _scan_game(connection, row, binding, move, engine, deadline, result):
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
        kind = "capture" if board.is_capture(recorded) else "quiet"
        if kind in result["attempted_kinds"]:
            continue
        result["witness_checked"] += 1
        if not candidate(board, recorded, deadline):
            continue
        result["attempted_kinds"].append(kind)
        result["native_attempted"] += 1
        measured = observe(board, recorded, engine, deadline)
        record(connection, row, binding, rows, ply, board, recorded, measured, result)
        if engine["failed"]:
            return False
        if len(result["attempted_kinds"]) == MAX_SEARCHES:
            break
    # An ambiguous returned search still counts as searched; every position must return.
    return result["native_completed"] - completed_before == len(candidates)


def visit(connection, row, binding, move, engine, deadline, result):
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
        complete = _scan_game(connection, row, binding, move, engine, deadline, result)
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
