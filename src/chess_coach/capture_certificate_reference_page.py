"""Read bounded active-session capture references."""

import json

from .capture_certificate_reference import _reference
from .learner_identity import normalize_identity
from .objective_capture_contract import GAIN_OBJECTIVE, TARGET_OBJECTIVE, TARGET_VERSION
from .objective_contract import OWNED_HISTORY


def session(db, subject, state):
    ceiling = (
        state[2]
        if state
        else db.connection.execute(
            "SELECT coalesce(max(rowid), 0) FROM unified_sessions"
        ).fetchone()[0]
    )
    clause = ""
    values = [normalize_identity(subject), ceiling]
    if state:
        clause = " AND started_at <= ? AND (started_at < ? OR (started_at = ? AND attempt_id > ?))"
        values.extend((state[0], state[0], state[0], state[1]))
    row = db.connection.execute(
        """SELECT attempt_id,started_at,subject,source_type,source_version,source_key,
        snapshot_hash,objective,provenance_json,status FROM unified_sessions
        INDEXED BY idx_unified_sessions_subject WHERE subject=? AND rowid<=?"""
        + clause
        + " ORDER BY started_at DESC,attempt_id LIMIT 1",
        values,
    ).fetchone()
    if row is None:
        return None, []
    return row, [row["started_at"], row["attempt_id"], ceiling]


def session_reference(row, subject):
    try:
        version = row["source_version"]
        objective, policy = (
            ("capture_named_target", TARGET_OBJECTIVE)
            if version == TARGET_VERSION
            else ("bounded_material_gain", GAIN_OBJECTIVE)
        )
        provenance = json.loads(row["provenance_json"])
        expected = (
            normalize_identity(subject),
            "own-game",
            objective,
            policy,
            OWNED_HISTORY,
            objective,
            3,
            row["source_key"],
        )
        actual = (
            row["subject"],
            row["source_type"],
            row["objective"],
            provenance.get("objective_version"),
            provenance.get("history_mode"),
            provenance.get("capture_objective"),
            provenance.get("gain_threshold"),
            str(provenance.get("evidence_id")),
        )
        if actual != expected or row["status"] not in {"active", "needs_verification"}:
            return None
        return _reference(row["subject"], version, row["source_key"], row["snapshot_hash"])
    except (ValueError, TypeError, KeyError, AttributeError):
        return None
