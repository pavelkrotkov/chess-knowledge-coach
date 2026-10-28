"""Filter current, explicitly reviewed, proven learner evidence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import cast

from .db import Database
from .mastery_candidate import prepare_candidate
from .mastery_sources import evidence_rows


def eligible_contexts(
    db: Database, subject: str, skill: str, operation: str, as_of: datetime
) -> tuple[list[dict], dict[str, int]]:
    excluded: Counter[str] = Counter()
    selected: dict[tuple[str, str], dict] = {}
    cache = {}
    for row in evidence_rows(db, subject, skill, operation):
        item, reason = prepare_candidate(db, row, subject, as_of, cache)
        if reason is not None:
            excluded[reason] += 1
            continue
        item = cast(dict, item)
        context = item["context"]
        key = (context["source"], context["source_id"])
        previous = selected.get(key)
        if previous is not None:
            excluded["duplicate_context"] += 1
        if previous is None or _rank(item) > _rank(previous):
            selected[key] = item
    return sorted(selected.values(), key=lambda item: item["evidence_id"]), dict(
        sorted(excluded.items())
    )


def _rank(item: dict) -> tuple:
    return item["observed_at"], item["ply"], item["evidence_id"]
