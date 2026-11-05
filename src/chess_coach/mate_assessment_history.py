"""Read bounded first-encounter short-mate assessment history."""

from .mastery_time import parse_utc
from .mate_assessment_groups import groups
from .mate_assessment_item import item
from .mate_assessment_rows import rows
from .recurrence_snapshot import read_snapshot
from .related_capture_position import prompt_key


def _collect(db, subject, corpus):
    selected, limited = rows(db, subject)
    items, seen, uncertain = [], set(), False
    for row in selected:
        try:
            when = parse_utc(row["started_at"])
            uncertain |= when is None or when.isoformat() != row["started_at"]
            key = prompt_key(row["prompt_fen"])
            if key in seen:
                continue
            seen.add(key)
            entry = item(db, row, corpus)
            if entry is None:
                continue
            items.append(entry)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError):
            uncertain = True
    return items, limited or uncertain


def report(db, subject, corpus):
    with read_snapshot(db):
        items, limited = _collect(db, subject, corpus)
        return {
            "items": list(reversed(items)),
            "groups": groups(items, limited),
            "limited": limited,
        }
