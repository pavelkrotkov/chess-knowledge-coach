"""Read a consistent plan without committing a caller's transaction."""

from contextlib import contextmanager

from .db import Database


@contextmanager
def plan_snapshot(db: Database):
    db.connection.execute("SAVEPOINT curriculum_plan")
    try:
        yield
        db.connection.execute("RELEASE SAVEPOINT curriculum_plan")
    except BaseException:
        db.connection.execute("ROLLBACK TO SAVEPOINT curriculum_plan")
        db.connection.execute("RELEASE SAVEPOINT curriculum_plan")
        raise
