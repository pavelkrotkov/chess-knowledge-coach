"""Resume bounded passes through capture evidence and direct references."""

from .capture_certificate_store import binding, location
from .recurrence_cursor import MAX_ID
from .recurrence_sources import evidence
from .short_mate_trend_store import read, write


def _valid(data, expected):
    before = data.get("before")
    return data.get("binding") == expected and type(before) is int and 1 <= before <= MAX_ID


def _session(value):
    if not isinstance(value, dict) or set(value) != {"after", "horizon"}:
        return {}
    if not all(
        isinstance(key, list)
        and len(key) == 2
        and all(isinstance(item, str) and item for item in key)
        for key in value.values()
    ):
        return {}
    return value


def _schedule(value):
    if not isinstance(value, dict) or set(value) != {"after", "horizon"}:
        return {}
    if not all(type(item) is int and 0 <= item < MAX_ID for item in value.values()):
        return {}
    return value if value["after"] <= value["horizon"] else {}


def state(db, subject, root):
    base = location(db, root, subject)
    if base is None:
        return None, {}
    path = base.with_name(base.name + ".progress.json")
    old = read(path, binding(db, subject), validator=_valid) or {}
    lane = old.get("lane", 0)
    return path, {
        "before": old.get("before", MAX_ID),
        "lane": lane if type(lane) is int and 0 <= lane < 3 else 0,
        "session": _session(old.get("session")),
        "schedule": _schedule(old.get("schedule")),
    }


def checkpoint(db, subject, root):
    path, current = state(db, subject, root)
    return path, current.get("before", MAX_ID)


def save(db, subject, path, current):
    write(path, {"binding": binding(db, subject), **current})


def page(db, subject, before, limit):
    rows, more = evidence(db, subject, "hanging_piece", "execute", before, limit=limit)
    if not rows and before != MAX_ID:
        return evidence(db, subject, "hanging_piece", "execute", MAX_ID, limit=limit)
    return rows, more


def next_before(rows, more, last):
    if not more and (not rows or last == rows[-1]["id"]):
        return MAX_ID
    return last
