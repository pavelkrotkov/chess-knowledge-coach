"""Validate a recorded recognition event without revealing active prompts."""

from .recognition_current import source
from .recognition_progress_event import outcome, validate
from .recognition_progress_scope import scope
from .related_capture_position import prompt_key


def item(db, row, corpus):
    result = {
        "attempt_id": row["attempt_id"],
        "started_at": row["started_at"],
        "outcome": "unavailable",
        "reason": "source or event unavailable",
        "scope": None,
    }
    if row["source_version"] != corpus or row["cue_status"] != "uncued":
        return {**result, "reason": "collection or cue policy differs"}
    try:
        proof = _current(db, row)
        if row["action"] is None:
            return {
                **result,
                "outcome": "incomplete",
                "reason": "not answered; familiarity is checked when opened",
            }
        return _completed(db, row, proof, result)
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return result


def _current(db, row):
    if prompt_key(row["prompt_fen"]) != row["prompt_key"]:
        raise ValueError("prompt changed")
    board, proof = source(db, row)
    if ("white" if board.turn else "black") != row["learner_color"]:
        raise ValueError("side changed")
    return proof


def _completed(db, row, proof, result):
    validate(row)
    result.update(
        current=True,
        scope=scope(db, row, proof),
        answered_at=row["answered_at"],
        opening=row["content_opening"],
        hints=int(bool(row["assisted"])),
        reveals=int(row["action"] == "reveal"),
        reason=None,
    )
    if result["scope"] is None:
        result["reason"] = "recorded difficulty or collection context unavailable"
    result["outcome"] = outcome(row, proof["kind"])
    return result
