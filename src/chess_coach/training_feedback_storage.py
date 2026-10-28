"""Persist unreviewed puzzle evidence and immutable completion results."""

import json
from typing import cast

from .db import Database
from .training_feedback_rules import MAPPER_VERSION, POLICY_VERSION


def record_evidence(db: Database, subject: str, timestamp: str, fact: dict) -> int:
    outcome = "success" if fact["played_checkmate"] else "failure"
    rationale = (
        "An unhinted legal move checkmates on the verified prompt board."
        if outcome == "success"
        else "An unhinted legal move did not checkmate when mate in one was requested and available."
    )
    context = {
        "source": "verified_puzzle",
        "training_objective": "Find mate in one.",
        "confidence_rationale": rationale,
        "policy_version": POLICY_VERSION,
        "mapper_version": MAPPER_VERSION,
        **fact,
    }
    cursor = db.connection.execute(
        """INSERT INTO evidence_mappings
        (position_id, skill, operation, outcome, confidence, source_facts_json,
         mapper_version, context_json, subject, observation_at, mapping_run_id, source_provenance)
        VALUES (NULL, 'mate_in_one', 'execute', ?, 1.0, '[]', ?, ?, ?, ?, NULL, 'training_attempt')""",
        (outcome, MAPPER_VERSION, json.dumps(context, sort_keys=True), subject, timestamp),
    )
    return cast(int, cursor.lastrowid)


def save_completion(
    db: Database,
    attempt_id: str,
    evidence_id: int | None,
    schedule_id: int,
    reason: str,
    request_hash: str,
    response: dict,
    timestamp: str,
) -> None:
    db.connection.execute(
        """INSERT INTO training_completions
        (attempt_id,evidence_id,training_attempt_id,policy_version,mapper_version,
         evidence_reason,request_hash,response_json,created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
        (
            attempt_id,
            evidence_id,
            schedule_id,
            POLICY_VERSION,
            MAPPER_VERSION,
            reason,
            request_hash,
            json.dumps(response, sort_keys=True),
            timestamp,
        ),
    )


def previous_completion(db: Database, attempt_id: str, request_hash: str) -> dict | None:
    row = db.connection.execute(
        "SELECT request_hash,response_json FROM training_completions WHERE attempt_id = ?",
        (attempt_id,),
    ).fetchone()
    if row is None:
        return None
    if row["request_hash"] != request_hash:
        raise ValueError("attempt was already completed with a different request")
    return json.loads(row["response_json"])
