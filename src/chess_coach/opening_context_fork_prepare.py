"""Prepare one immutable public fork certificate for an exact context choice."""

import time

from .fact_fingerprint import canonical, digest
from .opening_context_choice import select
from .opening_context_fork_binding import binding, key
from .opening_context_fork_scan import evaluate
from .opening_context_inventory import inventory
from .opening_public_comparison_source import board
from .opening_public_proof import PUBLICATION_WORKING
from .opening_public_proof_files import publish
from .opening_public_proof_source import PROOF_SECONDS, SECONDS
from .opening_queue_budget import BrowserBudget
from .opening_queue_files import MAX_BYTES
from .opening_recent_capacity import check as capacity
from .opening_unfamiliar_guard import check, start
from .tactical_study_path import planning


def _confirm(db, root, subject, value, expected, guard, deadline):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, deadline)
    check(db, root, subject, guard, budget)
    report = inventory(db, root, subject, deadline=deadline, annotation=False)
    item = select(report, value)
    if binding(item) != expected:
        raise ValueError("public fork selection changed")
    board(guard[1], item, budget)
    check(db, root, subject, guard, budget)


def prepare(db, root, subject, value):
    started = time.monotonic()
    deadline = started + SECONDS
    directory, _ = planning(root, subject)
    capacity(root, directory, deadline=deadline, working=PUBLICATION_WORKING)
    guard = start(db, root, subject)
    report = inventory(db, root, subject, deadline=deadline, annotation=False)
    item = select(report, value)
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, deadline)
    board(guard[1], item, budget)
    identity = binding(item)
    result = evaluate(guard[1], identity, min(deadline, started + PROOF_SECONDS))
    payload = {
        "binding": identity,
        "binding_sha256": digest(canonical(identity)),
        "coverage": result,
    }
    if len(canonical(payload).encode()) > MAX_BYTES - 512:
        payload["coverage"] = {"status": "incomplete", "reason": "result_exceeds_limit"}
    capacity(root, directory, deadline=deadline, working=PUBLICATION_WORKING)
    publish(
        directory,
        key(item["selection"]),
        payload,
        lambda: _confirm(db, root, subject, value, identity, guard, deadline),
    )
    return payload
