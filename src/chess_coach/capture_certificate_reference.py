"""Read bounded direct references to existing owned capture sources."""

import json
from copy import deepcopy

from .learner_identity import normalize_identity
from .objective_capture_contract import (
    GAIN_OBJECTIVE,
    GAIN_VERSION,
    TARGET_OBJECTIVE,
    TARGET_VERSION,
    valid_key,
)
from .objective_contract import OWNED_HISTORY


def session(db, subject, state):
    after = state.get("after")
    clause = ""
    values = [normalize_identity(subject)]
    if after is not None:
        clause = " AND (started_at < ? OR (started_at = ? AND attempt_id > ?))"
        values.extend((after[0], after[0], after[1]))
    row = db.connection.execute(
        """SELECT attempt_id,started_at,subject,source_type,source_version,source_key,
        snapshot_hash,objective,provenance_json,status FROM unified_sessions
        INDEXED BY idx_unified_sessions_subject WHERE subject=?"""
        + clause
        + " ORDER BY started_at DESC,attempt_id LIMIT 1",
        values,
    ).fetchone()
    if row is None:
        return None, {}
    marker = [row["started_at"], row["attempt_id"]]
    return row, {"after": marker, "horizon": state.get("horizon", marker)}


def schedule(db, state):
    ceiling = state.get("horizon")
    if ceiling is None:
        row = db.connection.execute(
            """SELECT id FROM training_items INDEXED BY idx_curriculum_capture_scheduled
            WHERE source_type='unified_owned_capture' AND skill='hanging_piece'
            AND operation='execute' ORDER BY id DESC LIMIT 1"""
        ).fetchone()
        if row is None:
            return None, {}
        ceiling = row["id"]
    row = db.connection.execute(
        """SELECT id,source_ref FROM training_items INDEXED BY idx_curriculum_capture_scheduled
        WHERE source_type='unified_owned_capture' AND skill='hanging_piece'
        AND operation='execute' AND id>? AND id<=? ORDER BY id LIMIT 1""",
        (state.get("after", 0), ceiling),
    ).fetchone()
    return (row, {"after": row["id"], "horizon": ceiling}) if row else (None, {})


def _reference(subject, version, key, snapshot):
    if (
        normalize_identity(subject) != subject
        or version not in {TARGET_VERSION, GAIN_VERSION}
        or not isinstance(key, str)
        or not valid_key(version, key)
        or not isinstance(snapshot, str)
        or len(snapshot) != 64
    ):
        return None
    return {"id": int(key), "version": version, "snapshot_hash": snapshot}


def session_reference(row, subject):
    try:
        version = row["source_version"]
        objective, policy = (
            ("capture_named_target", TARGET_OBJECTIVE)
            if version == TARGET_VERSION
            else ("bounded_material_gain", GAIN_OBJECTIVE)
        )
        provenance = json.loads(row["provenance_json"])
        if (
            row["subject"] != normalize_identity(subject)
            or row["status"] not in {"active", "needs_verification"}
            or row["source_type"] != "own-game"
            or row["objective"] != objective
            or provenance.get("objective_version") != policy
            or provenance.get("history_mode") != OWNED_HISTORY
            or provenance.get("capture_objective") != objective
            or provenance.get("gain_threshold") != 3
            or str(provenance.get("evidence_id")) != row["source_key"]
        ):
            return None
        return _reference(row["subject"], version, row["source_key"], row["snapshot_hash"])
    except (ValueError, TypeError, KeyError, AttributeError):
        return None


def schedule_reference(row, subject):
    try:
        owner, version, key, snapshot = json.loads(row["source_ref"])
        if owner != normalize_identity(subject) or version != TARGET_VERSION:
            return None
        return _reference(owner, version, key, snapshot)
    except (ValueError, TypeError, KeyError):
        return None


def matches(entry, reference):
    """Reconstruct the existing version-specific snapshot for an exact reference."""
    from .unified_source_current import snapshot_hash

    snapshot = deepcopy(entry["snapshot"])
    if reference["version"] == GAIN_VERSION:
        snapshot["objective"] = "bounded_material_gain"
        snapshot["provenance"]["objective_version"] = GAIN_OBJECTIVE
        snapshot["provenance"]["capture_objective"] = "bounded_material_gain"
    return snapshot_hash(snapshot) == reference["snapshot_hash"]
