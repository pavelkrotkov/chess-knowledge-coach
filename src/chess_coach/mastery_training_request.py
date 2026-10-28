"""Verify that a completion request assigned evidence to its learner."""

from .training_feedback_request import validate_request
from .training_feedback_rules import MAPPER_VERSION


def matches_request(row, evidence) -> bool:
    try:
        subject, request_hash = validate_request(
            row["attempt_id"],
            row["event_id"],
            row["submitted_move"],
            row["item_id"],
            evidence["subject"],
        )
    except (TypeError, ValueError):
        return False
    return subject == evidence["subject"] and request_hash == row["request_hash"]


def supported_mapper(row, evidence) -> bool:
    version = row["mapper_version"]
    if version not in {MAPPER_VERSION, "verified-puzzle-mate-v1"}:
        return False
    if evidence["mapper_version"] != version:
        return False
    return version != "verified-puzzle-mate-v1" or evidence["outcome"] == "success"
