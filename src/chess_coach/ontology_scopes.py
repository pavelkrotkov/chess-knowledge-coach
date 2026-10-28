"""Maintain independent ontology scopes without changing old review records."""

import json

from .db import Database
from .mapping_invalidation import supersede_mapping


def previous_scopes(db: Database, detector_version: str | None, groups: dict) -> None:
    rows = db.connection.execute(
        """SELECT * FROM mapping_runs WHERE producer = 'ontology' AND subject = 'unassigned' AND id IN
        (SELECT MAX(id) FROM mapping_runs WHERE producer = 'ontology'
         GROUP BY position_id, subject, operation, scope_key)"""
    ).fetchall()
    for row in rows:
        scope = _decode_scope(row["scope_key"])
        if scope is None or scope.get("detector_version") != detector_version:
            continue
        if "fact_id" not in scope:
            if row["status"] == "active":
                supersede_mapping(db, row["id"])
            continue
        groups.setdefault((row["position_id"], row["operation"], row["scope_key"]), [])


def _decode_scope(value: str) -> dict | None:
    try:
        scope = json.loads(value)
    except (TypeError, ValueError):
        return None
    return scope if isinstance(scope, dict) else None
