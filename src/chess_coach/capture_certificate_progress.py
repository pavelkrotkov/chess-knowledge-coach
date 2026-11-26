"""Resume one bounded pass through owner-scoped capture evidence."""

from .capture_certificate_store import binding, location
from .recurrence_cursor import MAX_ID
from .recurrence_sources import evidence
from .short_mate_trend_store import read, write


def _valid(data, expected):
    before = data.get("before")
    return data.get("binding") == expected and type(before) is int and 1 <= before <= MAX_ID


def checkpoint(db, subject, root):
    base = location(db, root, subject)
    if base is None:
        return None, MAX_ID
    path = base.with_name(base.name + ".progress.json")
    old = read(path, binding(db, subject), validator=_valid)
    return path, old["before"] if old else MAX_ID


def save(db, subject, path, before):
    write(path, {"binding": binding(db, subject), "before": before})


def page(db, subject, before, limit):
    rows, more = evidence(db, subject, "hanging_piece", "execute", before, limit=limit)
    if not rows and before != MAX_ID:
        return evidence(db, subject, "hanging_piece", "execute", MAX_ID, limit=limit)
    return rows, more


def next_before(rows, more, last):
    if not more and (not rows or last == rows[-1]["id"]):
        return MAX_ID
    return last
