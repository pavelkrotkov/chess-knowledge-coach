"""Atomically admit a selected transfer and create a unified session."""

from .unified_session_state import session_row, view
from .unified_sessions import _create
from .unified_source_current import require_current


def start_selected(db, *, attempt_id, subject, corpus_version, reference, resolver, binding_key):
    if not all(
        isinstance(v, str) and 0 < len(v) <= 256
        for v in (attempt_id, subject, corpus_version, reference)
    ):
        raise ValueError("invalid transfer identity")
    if db.connection.in_transaction:
        raise RuntimeError("cannot start during an existing transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        if db.connection.execute(
            "SELECT 1 FROM unified_sessions WHERE attempt_id=?", (attempt_id,)
        ).fetchone():
            raise ValueError("attempt ID already exists")
        source_type, version, key, binding, lines = resolver()
        _create(
            db,
            attempt_id,
            subject,
            source_type,
            version,
            key,
            provenance=binding,
            provenance_key=binding_key,
            line_filter=lines,
        )
        row = session_row(db, attempt_id, subject)
        require_current(db, row)
        result = view(row)
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise
