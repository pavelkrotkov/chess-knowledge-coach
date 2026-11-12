"""Derive a read-only opening course version from the checked report and chapters."""

from .fact_fingerprint import canonical, digest
from .opening_unfamiliar import explore_unfamiliar
from .opening_unfamiliar_lesson import lesson

VERSION = "unfamiliar-opening-course-v1"
SELECTED_VERSION = "unfamiliar-opening-course-v2"


def preview(db, root, learner, selection=None):
    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    if selection is None:
        report = explore_unfamiliar(db, root, learner)
    else:
        from .opening_unfamiliar_selected import selected

        report = selected(db, root, learner, selection)
    chapters = [
        lesson(report, color, report[color]) for color in ("white", "black") if report[color]
    ]
    payload = {"schema": VERSION, "report": report, "chapters": chapters}
    if selection is not None:
        payload.update(schema=SELECTED_VERSION, selection=selection)
    version = digest(canonical(payload))
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != before:
        raise ValueError("opening course source changed")
    result = {"version": version, "report": report, "chapters": chapters}
    if selection is not None:
        result["selection"] = selection
    return result
