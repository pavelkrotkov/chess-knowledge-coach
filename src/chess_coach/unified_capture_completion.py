"""Atomically record a qualified owned-capture learning completion."""

import json
from datetime import datetime

from .learner_identity import normalize_identity
from .training_review import review_item_in_transaction
from .training_transaction import training_transaction
from .unified_capture_learning import MAPPER, POLICY, proof
from .unified_session_state import now, session_row
from .unified_source_current import require_current


def _evidence(db, row, fact, outcome, observed):
    context = {
        "source": "unified_owned_capture",
        "policy_version": POLICY,
        "mapper_version": MAPPER,
        **fact,
    }
    return db.connection.execute(
        """INSERT INTO evidence_mappings
        (position_id,skill,operation,outcome,confidence,source_facts_json,mapper_version,
         context_json,subject,observation_at,mapping_run_id,source_provenance)
        VALUES(NULL,'hanging_piece','execute',?,1.0,'[]',?,?,?, ?,NULL,'training_attempt')""",
        (
            outcome,
            MAPPER,
            json.dumps(context, sort_keys=True),
            normalize_identity(row["subject"]),
            observed,
        ),
    ).lastrowid


def _save(db, row, item, event, fact, assisted, fingerprint):
    outcome = "success" if fact["status"] == "correct" else "failure"
    evidence = rating = schedule = None
    if not assisted:
        evidence = _evidence(db, row, fact, outcome, event["created_at"])
        rating = "good" if outcome == "success" else "again"
        schedule = review_item_in_transaction(
            db, item["item_id"], rating, reviewed_at=datetime.fromisoformat(event["created_at"])
        )
    due = db.connection.execute(
        "SELECT due FROM training_items WHERE id=?", (item["item_id"],)
    ).fetchone()[0]
    reason = "assisted_no_learning_update" if assisted else "unreviewed_evidence_recorded"
    response = {
        "outcome": outcome,
        "assistance": "assisted" if assisted else "unassisted",
        "reason": reason,
        "item_id": item["item_id"],
        "evidence_id": evidence,
        "rating": rating,
        "due": due,
        "policy_version": POLICY,
    }
    db.connection.execute(
        "INSERT INTO unified_training_completions VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            row["attempt_id"],
            event["event_id"],
            evidence,
            schedule["attempt_id"] if schedule else None,
            POLICY,
            MAPPER,
            outcome,
            response["assistance"],
            reason,
            fingerprint,
            json.dumps(response, sort_keys=True),
            now(),
        ),
    )
    return response


def complete(db, attempt_id, subject, *, event_id=None):
    if db.compat32:
        raise ValueError("learning is unavailable in compatibility mode")
    with training_transaction(db):
        row = session_row(db, attempt_id, subject)
        require_current(db, row)
        item, event, fact, assisted, fingerprint = proof(db, row, event_id)
        previous = db.connection.execute(
            "SELECT request_hash,response_json FROM unified_training_completions WHERE attempt_id=?",
            (attempt_id,),
        ).fetchone()
        if previous:
            if previous["request_hash"] != fingerprint:
                raise ValueError("completion conflicts with the recorded request")
            return json.loads(previous["response_json"])
        return _save(db, row, item, event, fact, assisted, fingerprint)
