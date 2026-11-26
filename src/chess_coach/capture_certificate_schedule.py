"""Read bounded scheduled capture references."""

import json

from .capture_certificate_reference import _reference
from .learner_identity import normalize_identity
from .objective_capture_contract import TARGET_VERSION


def schedule(db, state):
    ceiling = state[1] if state else None
    if ceiling is None:
        row = db.connection.execute(
            """SELECT id FROM training_items INDEXED BY idx_curriculum_capture_scheduled
            WHERE source_type='unified_owned_capture' AND skill='hanging_piece'
            AND operation='execute' ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            return None, []
        ceiling = row["id"]
    row = db.connection.execute(
        """SELECT id,source_ref FROM training_items INDEXED BY idx_curriculum_capture_scheduled
        WHERE source_type='unified_owned_capture' AND skill='hanging_piece'
        AND operation='execute' AND id>? AND id<=? ORDER BY id LIMIT 1""",
        (state[0] if state else 0, ceiling),
    ).fetchone()
    return (row, [row["id"], ceiling]) if row else (None, [])


def schedule_marker(value):
    if (
        isinstance(value, list)
        and len(value) == 2
        and all(type(x) is int and x >= 0 for x in value)
    ):
        return value if value[0] <= value[1] <= 2**63 - 1 else []
    return []


def schedule_reference(row, subject):
    try:
        owner, version, key, snapshot = json.loads(row["source_ref"])
        if owner != normalize_identity(subject) or version != TARGET_VERSION:
            return None
        return _reference(owner, version, key, snapshot)
    except (ValueError, TypeError, KeyError):
        return None
