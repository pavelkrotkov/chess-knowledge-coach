"""Bound the owned pin recurrence candidate scan."""

from collections import Counter
from datetime import UTC, datetime
from itertools import chain, zip_longest

from .recurrence_cursor import MAX_ID
from .recurrence_selection import consider
from .recurrence_sources import evidence

SCAN = 20


def candidates(db, learner, budget):
    pages, limited = [], False
    for outcome in ("failure", "success"):
        for skill in ("absolute_pin", "relative_pin"):
            with budget.scope(snapshot=False):
                page, more = evidence(
                    db, learner, skill, "prevent", MAX_ID, outcome=outcome, limit=SCAN
                )
            pages.append(page)
            limited |= more
    rows = filter(None, chain.from_iterable(zip_longest(*pages)))
    seen, cache, parts, excluded, result = set(), {}, {}, Counter(), []
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        with budget.scope(snapshot=False):
            item = consider(
                db,
                learner,
                row,
                {},
                cache,
                parts,
                excluded,
                datetime(2, 1, 1, tzinfo=UTC),
                datetime.now(UTC),
                datetime(1, 1, 1, tzinfo=UTC),
            )
        if item and item["family"] == "pin-prevent-mapper":
            result.append(item)
    return result, limited or bool(excluded["game replay limit"]), len(seen)
