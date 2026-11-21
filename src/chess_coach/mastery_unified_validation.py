"""Check the immutable evidence payload and observation timestamps."""

import json

from .learner_identity import normalize_identity
from .mastery_time import parse_utc
from .training_feedback_request import validate_request
from .unified_training_versions import MAPPER, POLICY


def check_evidence(evidence, completion, row, item, event, fact, assisted):
    _, fingerprint = validate_request(
        row["attempt_id"],
        event["event_id"],
        event["submitted_move"],
        item["item_id"],
        row["subject"],
    )
    expected = "success" if fact["played_checkmate"] else "failure"
    context = {
        "source": "unified_corpus_mate",
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
        "mate_in_one",
        "execute",
        "good" if expected == "success" else "again",
        context,
    )
    if actual != wanted:
        raise ValueError("learning lineage does not match")


def check_time(evidence, completion, row):
    observed = parse_utc(evidence["observation_at"])
    reviewed = parse_utc(completion["reviewed_at"])
    if (
        observed is None
        or observed != parse_utc(row["finished_at"])
        or reviewed is None
        or reviewed < observed
    ):
        raise ValueError("learning timestamps do not match")
