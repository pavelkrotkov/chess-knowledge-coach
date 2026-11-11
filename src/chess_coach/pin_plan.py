"""Find a current recurring owned pin-defense exercise within bounded work."""

import time
from collections import defaultdict

from .learner_identity import normalize_identity
from .objective_pin_prevent_contract import VERSION
from .objective_pin_prevent_source import resolve
from .opening_queue_budget import BrowserBudget
from .pin_plan_candidates import candidates
from .pin_plan_pattern import pattern
from .pin_plan_select import select

SOURCE_LIMIT = 20
SECONDS = 20.0


def _checked(db, subject, items, budget):
    groups = defaultdict(list)
    checked = 0
    for item in items[:SOURCE_LIMIT]:
        checked += 1
        try:
            with budget.scope(snapshot=False):
                snapshot = resolve(db, VERSION, str(item["id"]), subject)
                signature = pattern(snapshot, item)
            groups[signature].append((item, snapshot))
        except (ValueError, TypeError, KeyError, IndexError):
            continue
    return groups, checked


def report(db, subject):
    learner = normalize_identity(subject)
    if not learner:
        raise ValueError("pin subject unavailable")
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    items, limited, scanned = candidates(db, learner, budget)
    groups, checked = _checked(db, learner, items, budget)
    budget.check()
    return {
        "source": select(groups),
        "scanned": scanned,
        "checked": checked,
        "limited": limited or len(items) > checked,
    }
