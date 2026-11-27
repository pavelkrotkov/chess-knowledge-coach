"""Preflight a selected public experiment before any plan transaction."""

import time

from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity
from .opening_context_inventory import SECONDS, inventory
from .opening_context_launch_select import selected
from .opening_context_launch_watch import paths
from .opening_queue_budget import BrowserBudget
from .opening_study_source import fingerprint
from .opening_unfamiliar_guard import check, start


def preflight(db, root, subject, choice, *, budget=None):
    subject = normalize_identity(subject)
    if subject is None or db.connection.in_transaction:
        raise ValueError("opening launch unavailable")
    if budget is None:
        budget = BrowserBudget(db)
    elif budget.db is not db:
        raise ValueError("opening budget belongs to another connection")
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    guard = start(db, root, subject)
    base = inventory(db, root, subject, deadline=budget.expires, annotation=False, budget=budget)
    parent, _, _ = selected(base, choice, provisional=False)
    watched = sorted(paths(root, subject, parent))
    before = fingerprint(watched)
    budget.check()
    report = inventory(db, root, subject, deadline=budget.expires, budget=budget)
    current, item, admission = selected(report, choice, provisional=True)
    check(db, root, subject, guard, budget)
    if sorted(paths(root, subject, current)) != watched or fingerprint(watched) != before:
        raise ValueError("opening context changed")
    inputs = [
        subject,
        choice,
        report["sample_identity"],
        report["reference_index_sha256"],
        item["selection"],
        item["source"],
        current["fit"],
        current["development"],
        before,
    ]
    # Keep existing developmental-token bindings while distinguishing a fit-only admission.
    if admission == "fit":
        inputs.append("fit")
    binding = digest(canonical(inputs))
    return {
        "budget": budget,
        "guard": guard,
        "paths": watched,
        "fingerprint": before,
        "binding": binding,
        "parent": current,
        "item": item,
        "choice": choice,
        "admission": admission,
        "report": report,
    }
