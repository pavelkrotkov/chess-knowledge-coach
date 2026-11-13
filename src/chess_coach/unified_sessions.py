"""Start immutable source snapshots without changing legacy puzzle attempts."""

import json

from .objective_promotion_admission import admit as admit_promotion
from .related_session_filter import apply_filter
from .unified_corpus_mate import apply as apply_goal
from .unified_corpus_mate import check_existing, validate_goal
from .unified_session_state import now, session_row, view
from .unified_source_current import require_current, snapshot_hash
from .unified_sources import resolve_source


def start(db, *, attempt_id, subject, source_type, version, key, goal=None):
    validate_goal(source_type, goal)
    if not all(
        isinstance(v, str) and 0 < len(v) <= 256
        for v in (attempt_id, subject, source_type, version, key)
    ):
        raise ValueError("practice identity is invalid")
    if db.connection.in_transaction:
        raise RuntimeError("cannot start during an existing transaction")
    try:
        db.connection.execute("BEGIN IMMEDIATE")
        old = db.connection.execute(
            "SELECT * FROM unified_sessions WHERE attempt_id=?", (attempt_id,)
        ).fetchone()
        if old:
            if (old["subject"], old["source_type"], old["source_version"], old["source_key"]) != (
                subject,
                source_type,
                version,
                key,
            ):
                raise ValueError("attempt ID belongs to another source")
            # An attempt ID remains bound to its original announced goal.
            check_existing(old, goal)
            require_current(db, old)
        else:
            _create(db, attempt_id, subject, source_type, version, key, goal=goal)
        row = session_row(db, attempt_id, subject)
        result = view(row)
        db.connection.commit()
        return result
    except BaseException:
        db.connection.rollback()
        raise


def _create(
    db,
    attempt_id,
    subject,
    source_type,
    version,
    key,
    provenance=None,
    provenance_key="related_capture",
    line_filter=None,
    goal=None,
):
    snapshot = resolve_source(db, source_type, version, key, subject=subject)
    apply_goal(db, snapshot, source_type, version, key, goal)
    apply_filter(snapshot, provenance, provenance_key, line_filter)
    if source_type == "public":
        admit_promotion(snapshot)
    if provenance is not None:
        snapshot["provenance"][provenance_key] = provenance
    fingerprint = snapshot_hash(snapshot)
    lines = [line.split() for line in snapshot["lines"]]
    db.connection.execute(
        """INSERT INTO unified_sessions
        (attempt_id,subject,source_type,source_version,source_key,snapshot_hash,prompt_fen,
        learner_color,objective,lines_json,provenance_json,current_fen,candidates_json,next_index,status,started_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,0,\u0027active\u0027,?)""",
        (
            attempt_id,
            subject,
            source_type,
            version,
            key,
            fingerprint,
            snapshot["prompt_fen"],
            snapshot["learner_color"],
            snapshot["objective"],
            json.dumps(lines),
            json.dumps(snapshot["provenance"], sort_keys=True),
            snapshot["prompt_fen"],
            json.dumps(list(range(len(lines)))),
            now(),
        ),
    )
