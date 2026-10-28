"""Filter current, explicitly reviewed, proven learner evidence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import cast

from .db import Database
from .mastery_candidate import prepare_candidate
from .mastery_context_dedup import select_contexts
from .mastery_sources import evidence_rows


def eligible_contexts(
    db: Database, subject: str, skill: str, operation: str, as_of: datetime
) -> tuple[list[dict], dict[str, int]]:
    excluded: Counter[str] = Counter()
    items = []
    cache = {}
    for row in evidence_rows(db, subject, skill, operation):
        item, reason = prepare_candidate(db, row, subject, as_of, cache)
        if reason is not None:
            excluded[reason] += 1
        else:
            items.append(cast(dict, item))
    selected = select_contexts(items, excluded)
    return selected, dict(sorted(excluded.items()))
