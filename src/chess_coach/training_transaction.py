"""Atomic scheduling without committing a caller-owned transaction."""

from contextlib import contextmanager

from .db import Database


@contextmanager
def training_transaction(db: Database):
    nested = db.connection.in_transaction
    db.connection.execute("SAVEPOINT training_batch" if nested else "BEGIN IMMEDIATE")
    try:
        yield
        if nested:
            db.connection.execute("RELEASE SAVEPOINT training_batch")
        else:
            db.connection.commit()
    except BaseException:
        if nested:
            db.connection.execute("ROLLBACK TO SAVEPOINT training_batch")
            db.connection.execute("RELEASE SAVEPOINT training_batch")
        else:
            db.connection.rollback()
        raise
