"""Record an immutable first response after a guarded familiarity check."""

from .recognition_current import source
from .recognition_novelty import novel
from .recognition_store import _now, row


def respond(db, subject, attempt, action, answer):
    _valid(action, answer)
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    saved = row(db, subject, attempt)
    source(db, saved)
    if saved["action"] is None:
        novel(db, saved)
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            raise ValueError("recognition source changed")
        saved = row(db, subject, attempt)
        source(db, saved)
        if saved["action"] is not None:
            if (saved["action"], saved["answer"]) != (action, answer):
                raise ValueError("recognition response is immutable")
        else:
            db.connection.execute(
                "INSERT INTO recognition_events VALUES(?,?,?,?,?)",
                (attempt, action, answer, int(action == "reveal"), _now()),
            )
        db.connection.commit()
    except BaseException:
        db.connection.rollback()
        raise


def _valid(action, answer):
    if action == "answer" and answer in {"capture", "mate", "uncertain"}:
        return
    if action == "reveal" and answer is None:
        return
    raise ValueError("recognition response unavailable")
