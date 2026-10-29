"""Keep one report on a consistent SQLite snapshot without owning caller work."""

from contextlib import contextmanager


@contextmanager
def read_snapshot(db):
    if db.connection.in_transaction:
        yield
        return
    db.connection.execute("BEGIN")
    try:
        yield
    finally:
        db.connection.rollback()
