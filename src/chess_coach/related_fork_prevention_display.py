"""Expose practice entry only for an eligible pre-existing knight source."""

from flask import render_template

from .fork_defense_mastery_root import supported_threat
from .related_fork_avoidance_display import available as avoidance_available
from .web_board import board_rows


def available(evidence):
    try:
        if evidence["fork_defense_currentness"] != "current" or evidence["operation"] != "prevent":
            return False
        if evidence["review_status"] not in {"accepted", "unreviewed"}:
            return False
        payload = evidence["facts"][0]["payload"]
        if (
            payload["outcome"] != "success"
            and payload.get("threat_origin") != "positional_before_played"
        ):
            return False
        return supported_threat(evidence["decision_fen"], payload)
    except (ValueError, TypeError, KeyError, IndexError):
        return False


def render_evidence(evidence):
    evidence["anchored_fork_prevention"] = available(evidence)
    evidence["created_fork_avoidance"] = avoidance_available(evidence)
    return render_template(
        "evidence.html", evidence=evidence, board=board_rows(evidence["decision_fen"])
    )
