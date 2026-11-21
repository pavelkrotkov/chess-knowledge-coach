"""Recheck the exact owned-capture evidence lineage for reviewed mastery use."""

import json

import chess

from .learner_identity import normalize_identity
from .mastery_position import position_key
from .mastery_time import parse_utc
from .unified_capture_learning import MAPPER, POLICY, proof
from .unified_source_current import require_current


def lineage(db, evidence, completion, row):
    require_current(db, row)
    item, event, fact, assisted, fingerprint = proof(db, row, completion["event_id"])
    expected = "success" if fact["status"] == "correct" else "failure"
    context = {
        "source": "unified_owned_capture",
        "policy_version": POLICY,
        "mapper_version": MAPPER,
        **fact,
    }
    actual = (
        assisted,
        completion["assistance"],
        completion["outcome"],
        evidence["outcome"],
        completion["policy_version"],
        completion["mapper_version"],
        evidence["mapper_version"],
        completion["reason"],
        completion["request_hash"],
        evidence["subject"],
        completion["item_id"],
        evidence["skill"],
        evidence["operation"],
        completion["rating"],
        json.loads(completion["evidence_context"]),
    )
    wanted = (
        False,
        "unassisted",
        expected,
        expected,
        POLICY,
        MAPPER,
        MAPPER,
        "unreviewed_evidence_recorded",
        fingerprint,
        normalize_identity(row["subject"]),
        item["item_id"],
        "hanging_piece",
        "execute",
        "good" if expected == "success" else "again",
        context,
    )
    observed = parse_utc(event["created_at"])
    if (
        actual != wanted
        or observed is None
        or parse_utc(evidence["observation_at"]) != observed
        or parse_utc(completion["reviewed_at"]) != observed
    ):
        raise ValueError("capture learning lineage does not match")
    return {
        "kind": "training",
        "attempt_id": row["attempt_id"],
        "prompt_fen": position_key(chess.Board(row["prompt_fen"])),
    }
