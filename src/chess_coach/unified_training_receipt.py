"""Store a qualified completion and its optional evidence and FSRS review."""

import json
from datetime import datetime

from .learner_identity import normalize_identity
from .unified_session_state import now
from .unified_training_versions import MAPPER, POLICY


def _evidence(db, row, fact, timestamp):
    outcome = "success" if fact["played_checkmate"] else "failure"
    context = {
        "source": "unified_corpus_mate",
        "policy_version": POLICY,
        "mapper_version": MAPPER,
        **fact,
    }
    cursor = db.connection.execute(
        """INSERT INTO evidence_mappings
        (position_id,skill,operation,outcome,confidence,source_facts_json,mapper_version,
         context_json,subject,observation_at,mapping_run_id,source_provenance)
        VALUES(NULL,'mate_in_one','execute',?,1.0,'[]',?,?,?, ?,NULL,'training_attempt')""",
        (
            outcome,
            MAPPER,
            json.dumps(context, sort_keys=True),
            normalize_identity(row["subject"]),
            timestamp,
        ),
    )
    return cursor.lastrowid


def _schedule(db, row, item, fact, review):
    observed = row["finished_at"]
    if not observed:
        raise ValueError("terminal time is unavailable")
    evidence = _evidence(db, row, fact, observed)
    rating = "good" if fact["played_checkmate"] else "again"
    schedule = review(db, item["item_id"], rating, reviewed_at=datetime.fromisoformat(now()))
    return evidence, rating, schedule


def save(db, row, item, event, fact, assisted, request_hash, review):
    outcome = "success" if fact["played_checkmate"] else "failure"
    evidence, rating, schedule = (None, None, None)
    if not assisted:
        evidence, rating, schedule = _schedule(db, row, item, fact, review)
    due = db.connection.execute(
        "SELECT due FROM training_items WHERE id=?", (item["item_id"],)
    ).fetchone()[0]
    reason = "assisted_no_learning_update" if assisted else "unreviewed_evidence_recorded"
    result = {
        "outcome": outcome,
        "assistance": "assisted" if assisted else "unassisted",
        "reason": reason,
        "item_id": item["item_id"],
        "evidence_id": evidence,
        "rating": rating,
        "due": due,
        "policy_version": POLICY,
    }
    schedule_id = schedule["attempt_id"] if schedule else None
    db.connection.execute(
        """INSERT INTO unified_training_completions
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            row["attempt_id"],
            event["event_id"],
            evidence,
            schedule_id,
            POLICY,
            MAPPER,
            outcome,
            result["assistance"],
            reason,
            request_hash,
            json.dumps(result, sort_keys=True),
            now(),
        ),
    )
    return result
