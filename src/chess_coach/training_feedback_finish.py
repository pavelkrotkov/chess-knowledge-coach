"""Atomically compose evidence, FSRS and completion history."""

from datetime import datetime
from typing import cast

from .db import Database
from .training_feedback_rules import MAPPER_VERSION, POLICY_VERSION, assessment, rating_for
from .training_feedback_storage import record_evidence, save_completion
from .training_review import review_item_in_transaction


def complete_feedback(
    db: Database, session, item, result: dict, move: str, subject: str, request_hash: str
) -> dict:
    reason, fact = assessment(session, result, move, item)
    timestamp = result["finished_at"]
    evidence_id = record_evidence(db, subject, timestamp, fact) if fact is not None else None
    rating = rating_for(session, result)
    schedule = review_item_in_transaction(
        db, item["id"], rating, reviewed_at=datetime.fromisoformat(timestamp)
    )
    response = {
        **result,
        "training": {
            "item_id": item["id"],
            "rating": rating,
            "attempt_id": cast(int, schedule["attempt_id"]),
            "evidence_id": evidence_id,
            "evidence_reason": reason,
            "policy_version": POLICY_VERSION,
            "mapper_version": MAPPER_VERSION,
        },
    }
    save_completion(
        db,
        session["attempt_id"],
        evidence_id,
        cast(int, schedule["attempt_id"]),
        reason,
        request_hash,
        response,
        timestamp,
    )
    return response
