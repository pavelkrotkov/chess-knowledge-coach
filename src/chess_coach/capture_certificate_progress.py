"""Resume bounded passes through capture evidence and direct references."""

from .capture_certificate_reference import session_marker
from .capture_certificate_schedule import schedule_marker
from .capture_certificate_store import binding, location
from .learner_identity import normalize_identity
from .recurrence_cursor import MAX_ID
from .short_mate_trend_store import read, write


def _valid(data, expected):
    before = data.get("before")
    return data.get("binding") == expected and type(before) is int and 1 <= before <= MAX_ID


def checkpoint(db, subject, root):
    base = location(db, root, subject)
    if base is None:
        return None, {}
    path = base.with_name(base.name + ".progress.json")
    old = read(path, binding(db, subject), validator=_valid) or {}
    lane = old.get("lane", 0)
    return path, {
        "before": old.get("before", MAX_ID),
        "lane": lane if type(lane) is int and 0 <= lane < 3 else 0,
        "session": session_marker(old.get("session")),
        "schedule": schedule_marker(old.get("schedule")),
    }


def save(db, subject, path, current):
    write(path, {"binding": binding(db, subject), **current})


def next_evidence(db, subject, before):
    row = db.connection.execute(
        """SELECT id FROM evidence_mappings INDEXED BY idx_curriculum_evidence
        WHERE subject=? AND skill='hanging_piece' AND operation='execute' AND id<?
        ORDER BY id DESC LIMIT 1""",
        (normalize_identity(subject), before),
    ).fetchone()
    return (row, row["id"]) if row else (None, MAX_ID)
