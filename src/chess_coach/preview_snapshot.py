"""Bound a material preview to a consistent, read-only SQLite snapshot."""

from contextlib import contextmanager

from .preview_history import PreviewHistory


@contextmanager
def preview_history(db, learner):
    connection = db.connection
    previous = connection.execute("PRAGMA query_only").fetchone()[0]
    connection.execute("PRAGMA query_only=ON")
    try:
        connection.execute("SAVEPOINT material_preview")
        history = PreviewHistory(db, learner)
        try:
            yield history
        finally:
            history.clear()
            connection.execute("RELEASE material_preview")
    finally:
        connection.execute(f"PRAGMA query_only={int(previous)}")
