"""Complete one owner-scoped, bounded scheduled-prompt scan."""

from .curriculum_scheduled_query import scheduled_rows
from .curriculum_unified_reference import prompt


def scan(db, state, wanted, budget):
    limit = state["scan_limit"]
    rows = scheduled_rows(db, 0, limit)
    if len(rows) > limit:
        raise ValueError("scheduled scan incomplete")
    started = set()
    for row in rows:
        budget.check()
        visible, key = prompt(db, row, state["subject_hash"], check=budget.check)
        if visible and key is None:
            raise ValueError("scheduled prompt unavailable")
        if visible and key in wanted:
            started.add(key)
    budget.check()
    budget.renewal_examined = len(rows)
    return wanted - started
