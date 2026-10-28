"""Atomic classification batches without committing a caller's transaction."""

from contextlib import contextmanager

from .db import Database


@contextmanager
def classification_transaction(db: Database):
    nested = db.connection.in_transaction
    db.connection.execute("SAVEPOINT classification_batch" if nested else "BEGIN IMMEDIATE")
    try:
        yield
        if nested:
            db.connection.execute("RELEASE SAVEPOINT classification_batch")
        else:
            db.connection.commit()
    except BaseException:
        if nested:
            db.connection.execute("ROLLBACK TO SAVEPOINT classification_batch")
            db.connection.execute("RELEASE SAVEPOINT classification_batch")
        else:
            db.connection.rollback()
        raise
