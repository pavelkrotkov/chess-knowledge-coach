"""Derive a read-only opening course version from the checked report and chapters."""

from .fact_fingerprint import canonical, digest
from .opening_unfamiliar import explore_unfamiliar
from .opening_unfamiliar_lesson import lesson

VERSION = "unfamiliar-opening-course-v1"


def preview(db, root, learner):
    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    report = explore_unfamiliar(db, root, learner)
    chapters = [
        lesson(report, color, report[color]) for color in ("white", "black") if report[color]
    ]
    payload = {"schema": VERSION, "report": report, "chapters": chapters}
    version = digest(canonical(payload))
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != before:
        raise ValueError("opening course source changed")
    return {"version": version, "report": report, "chapters": chapters}
