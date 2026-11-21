"""Bounded, typed snapshots of run-dependent tables and resolved runs."""

import hashlib
import pickle
import sqlite3

from .analysis_history_tables import dependent_tables
from .recovery_fidelity import MAX_RECORD_BYTES
from .recovery_fidelity_budget import preflight
from .recovery_fidelity_query import query_for


def _digest(connection, query, deadline):
    result = hashlib.sha256()
    count = 0
    for row in connection.execute(query):
        deadline.check()
        value = pickle.dumps(tuple(row), protocol=4)
        result.update(len(value).to_bytes(8, "big"))
        result.update(value)
        count += 1
    return count, result.digest()


def dependents(connection, deadline):
    """Fingerprint every transitive foreign-key dependent, including hidden rowids."""
    old_factory = connection.text_factory
    old_limit = connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_RECORD_BYTES)
    try:
        connection.text_factory = bytes
        result = {}
        for name, without_rowid in dependent_tables(connection):
            deadline.check()
            preflight(connection, name, deadline, MAX_RECORD_BYTES)
            query = query_for(connection, name, without_rowid)
            result[name] = _digest(connection, query, deadline)
        return result
    finally:
        connection.text_factory = old_factory
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, old_limit)


def resolved(connection, deadline):
    """Fingerprint the ordered public run view, including all original columns."""
    return _digest(connection, "SELECT * FROM analysis_runs_read ORDER BY id", deadline)
