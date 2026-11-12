"""Gather bounded recognition history while checking coverage and dates."""

import time

from .mastery_time import parse_utc
from .recognition_progress_groups import groups
from .recognition_progress_item import item
from .recognition_progress_rows import rows
from .related_capture_position import prompt_key


def collect(db, subject, corpus, until):
    selected, limited = rows(db, subject)
    items, seen = [], set()
    for row in selected:
        if time.monotonic() >= until:
            raise ValueError("recognition history deadline reached")
        when = parse_utc(row["started_at"])
        limited |= when is None or when.isoformat() != row["started_at"]
        try:
            key = prompt_key(row["prompt_fen"])
            entry = item(db, row, corpus)
            if key in seen:
                entry.update(
                    outcome="repeated", scope=None, reason="prompt was already encountered"
                )
            seen.add(key)
            items.append(entry)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            limited = True
            items.append(
                {
                    "attempt_id": row["attempt_id"],
                    "started_at": row["started_at"],
                    "outcome": "unavailable",
                    "reason": "history unavailable",
                    "scope": None,
                }
            )
    return {"items": list(reversed(items)), "groups": groups(items, limited), "limited": limited}
