"""Read-only, source-bound inspection of one proposed protection response."""

import sqlite3
import time

from .material_exchange_rules import MAX_EXCHANGE_NODES, MAX_EXCHANGE_PLIES
from .preview_snapshot import preview_history
from .style_guard_source import inspect_source
from .style_schedule_budget import BudgetExceeded, history_budget

VERSION = "protection-exchange-inspection-v1"
SECONDS = 8.0
NODE_LIMIT = MAX_EXCHANGE_NODES
PLIES = MAX_EXCHANGE_PLIES


def inspect(db, learner, evidence_id, response):
    start = time.monotonic()
    deadline = start + SECONDS
    nodes = [0]

    def check():
        if time.monotonic() >= deadline:
            raise TimeoutError

    def node():
        check()
        if nodes[0] >= NODE_LIMIT:
            raise BudgetExceeded("exchange limit")

    db.connection.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    try:
        generation = db.connection.execute("PRAGMA data_version").fetchone()[0]
        with history_budget(deadline=deadline), preview_history(db, learner) as history:
            result = inspect_source(
                db, learner, evidence_id, response, history, nodes, check, node, start, SECONDS
            )
        check()
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != generation:
            result = {"status": "unknown", "reason": "source_changed"}
    except TimeoutError:
        result = {"status": "unknown", "reason": "deadline"}
    except BudgetExceeded:
        result = {"status": "unknown", "reason": "work_limit"}
    except (ValueError, TypeError, KeyError, IndexError, sqlite3.Error):
        result = {"status": "unknown", "reason": "inspection_unavailable"}
    finally:
        db.connection.set_progress_handler(None, 0)
    return {
        "version": VERSION,
        **result,
        "coverage": {"exchange_nodes": nodes[0], "node_limit": NODE_LIMIT, "max_plies": PLIES},
        "limits": {
            "deadline_seconds": SECONDS,
            "elapsed_seconds": round(time.monotonic() - start, 6),
        },
        "boundary": "Conditional same-square exchanges only; other quiet moves, compensation and later play are not assessed.",
    }
