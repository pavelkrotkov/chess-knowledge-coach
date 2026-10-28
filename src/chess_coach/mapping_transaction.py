"""Atomic mapping batches, including callers with an existing transaction."""

from contextlib import contextmanager

from .db import Database


@contextmanager
def mapping_transaction(db: Database):
    nested = db.connection.in_transaction
    db.connection.execute("SAVEPOINT evidence_batch" if nested else "BEGIN IMMEDIATE")
    try:
        yield
        if nested:
            db.connection.execute("RELEASE SAVEPOINT evidence_batch")
        else:
            db.connection.commit()
    except BaseException:
        if nested:
            db.connection.execute("ROLLBACK TO SAVEPOINT evidence_batch")
            db.connection.execute("RELEASE SAVEPOINT evidence_batch")
        else:
            db.connection.rollback()
        raise
