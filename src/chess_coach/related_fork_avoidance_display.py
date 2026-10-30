"""Expose created-fork practice only for eligible source evidence."""

from .fork_defense_mastery_root import supported_threat


def available(evidence):
    try:
        if evidence["fork_defense_currentness"] != "current" or evidence["operation"] != "prevent":
            return False
        if evidence["review_status"] not in {"accepted", "unreviewed"}:
            return False
        payload = evidence["facts"][0]["payload"]
        return (
            payload["outcome"] == "failure"
            and payload.get("threat_origin") == "created_by_played_move"
            and supported_threat(evidence["decision_fen"], payload)
        )
    except (ValueError, TypeError, KeyError, IndexError):
        return False
