"""Prepare and retain one bounded comparison of an exact public candidate."""

import json
import time

from .deep_execution_lock import deep_lock
from .opening_context_choice import select
from .opening_context_inventory import inventory
from .opening_public_comparison_engine import analyze, configuration
from .opening_public_comparison_read import VERSION, key
from .opening_public_comparison_source import board
from .opening_public_comparison_view import view
from .opening_public_proof import PUBLICATION_WORKING
from .opening_public_proof_files import publish
from .opening_queue_budget import BrowserBudget
from .opening_queue_files import MAX_BYTES
from .opening_recent_capacity import check as capacity
from .opening_unfamiliar_guard import check, start
from .purpose_config import WORKER_SECONDS
from .tactical_study_path import planning


def _confirm(db, root, subject, guard, budget, config, public_board):
    check(db, root, subject, guard, budget)
    _, current = configuration(config["engine_path"], public_board)
    if current != config:
        raise ValueError("public engine configuration changed")
    budget.check()


def _bounded(selection, config, result):
    value = {"version": VERSION, "selection": selection, "configuration": config, "result": result}
    encoded = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    if len(encoded) > MAX_BYTES - 512:
        value["result"] = {"status": "insufficient", "reason": "result_exceeds_limit"}
    return value


def prepare(db, root, subject, token, engine):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + WORKER_SECONDS)
    directory, _ = planning(root, subject)
    capacity(root, directory, deadline=budget.expires, working=PUBLICATION_WORKING)
    with deep_lock(db.path):
        guard = start(db, root, subject)
        report = inventory(db, root, subject, deadline=budget.expires)
        item = select(report, token)
        public_board = board(guard[1], item, budget)
        config, result = analyze(public_board, item["selection"]["move"], engine, budget.expires)
        payload = _bounded(item["selection"], config, result)
        capacity(root, directory, deadline=budget.expires, working=PUBLICATION_WORKING)
        publish(
            directory,
            key(item["selection"]),
            payload,
            lambda: _confirm(db, root, subject, guard, budget, config, public_board),
        )
    return view(payload, public_board)
