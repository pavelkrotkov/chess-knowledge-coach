"""Narrow verified-puzzle evidence and deterministic scheduling policy."""

from .training_feedback_prompt import verified_mate

POLICY_VERSION = "verified-puzzle-schedule-v1"
MAPPER_VERSION = "verified-puzzle-mate-v2"


def assessment(session, result: dict, move: str, item) -> tuple[str, dict | None]:
    if session["hints_used"]:
        return "hint_used", None
    if item["skill"] != "mate_in_one" or item["operation"] != "execute":
        return "unsupported_training_skill", None
    if session["next_index"] != 1:
        return "unsupported_puzzle_decision", None
    return _assess_move(session, result, move)


def rating_for(session, result: dict) -> str:
    if result["status"] == "failed":
        return "again"
    return "hard" if session["hints_used"] else "good"


def _assess_move(session, result: dict, move: str) -> tuple[str, dict | None]:
    fact = verified_mate(session, move)
    if fact is not None and fact["played_checkmate"] and result["status"] == "solved":
        return "verified_mate_in_one", fact
    if fact is not None and not fact["played_checkmate"] and result["status"] == "failed":
        return "missed_mate_in_one", fact
    if result["status"] == "failed":
        return "failed_attempt", None
    return "unsupported_puzzle_decision", None
