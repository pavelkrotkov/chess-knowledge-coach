"""Select one bounded prepared replay from repeated protection markers."""

import time

from .capture_plan_sources import _groups
from .learner_identity import normalize_identity
from .opening_queue_budget import BrowserBudget
from .protection_plan_select import select

SECONDS = 20.0


def _rank(groups):
    repeated = [
        items for items in groups.values() if len({item["game_key"] for item in items}) >= 2
    ]
    return sorted(
        repeated, key=lambda items: (-len({x["game_key"] for x in items}), -items[0]["id"])
    )


def report(db, subject):
    learner = normalize_identity(subject)
    if not learner:
        raise ValueError("protection subject unavailable")
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    groups, limited, scanned = _groups(db, learner, check=budget.check, operation="prevent")
    ranked = _rank(groups)
    selected, checked = select(db, subject, ranked, budget)
    budget.check()
    return {
        "source": selected,
        "groups": len(ranked),
        "scanned": scanned,
        "checked": checked,
        "unavailable": checked - int(selected is not None),
        "limited": limited,
        "partial": limited or sum(len(items) for items in ranked) > checked,
    }
