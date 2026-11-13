"""Bound any current material-protection evidence and review at one decision."""

import json

from .fact_fingerprint import canonical, digest
from .learner_identity import normalize_identity
from .material_contract import PRODUCER
from .protection_game_review_evidence import checked


def _active(db, game_id):
    rows = db.connection.execute(
        """SELECT p.id AS position_id,d.id,d.detector_version,d.input_json,
        f.id AS fact_id,f.position_id AS fact_position,
        f.detector_version AS fact_version,f.fact_type,f.payload_json
        FROM positions p JOIN detector_runs_read d ON d.position_id=p.id
        AND d.producer=? AND d.status='active'
        LEFT JOIN detector_facts f ON f.run_id=d.id
        WHERE p.game_id=? ORDER BY p.ply,f.id LIMIT 1001""",
        (PRODUCER, game_id),
    ).fetchall()
    if len(rows) > 1000 or len({row["position_id"] for row in rows}) != len(rows):
        raise ValueError("protection review coverage unavailable")
    return rows


def _one(db, game_id, subject, row):
    position = row["position_id"]
    if row["fact_id"] is None:
        return None
    try:
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            raise ValueError
        if payload.get("kind") != "material_protection":
            return None
        return [position, "current", checked(db, position, game_id, subject, row, payload)]
    except (ValueError, TypeError, KeyError, IndexError):
        return [position, "unavailable"]


def binding(db, game_id, learner):
    subject = normalize_identity(learner)
    if not subject:
        raise ValueError("learner unavailable")
    values = [value for row in _active(db, game_id) if (value := _one(db, game_id, subject, row))]
    blocked = {value[0] for value in values if value[1] == "unavailable"}
    return digest(canonical(values)), blocked
