"""Prepare bounded provisional own-game pawn exercises from current evidence."""

from .evidence_review import inspect_evidence
from .learner_identity import normalize_identity
from .pawn_coach_contract import MAPPER
from .pawn_practice_keys import evidence_id

VERSION = "pawn-own-v1"


def _view(db, evidence_id, subject):
    owner = db.connection.execute(
        "SELECT subject FROM evidence_mappings WHERE id=?", (evidence_id,)
    ).fetchone()
    if owner is None or owner["subject"] != normalize_identity(subject):
        raise ValueError("practice source unavailable")
    evidence = inspect_evidence(db, evidence_id)
    if (
        evidence["mapping_producer"] != MAPPER
        or evidence["pawn_source_currentness"] != "current"
        or evidence["review_status"] not in {"accepted", "unreviewed"}
        or evidence["outcome"] not in {"success", "failure"}
    ):
        raise ValueError("practice source unavailable")
    return evidence


def _objective(evidence):
    return "pawn_win" if evidence["context"]["pawn_observation"]["root_wdl"] == 1 else "pawn_draw"


def resolve(db, key, subject):
    evidence = _view(db, evidence_id(key), subject)
    fact = evidence["context"]["pawn_observation"]
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence["id"],),
    ).fetchone()
    return {
        "prompt_fen": evidence["decision_fen"],
        "learner_color": "white" if evidence["decision_fen"].split()[1] == "w" else "black",
        "objective": _objective(evidence),
        "lines": [move["uci"] for move in fact["preserving"]],
        "provenance": {
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "review_event_id": review["id"] if review else None,
            "review_status": evidence["review_status"],
            "source_fingerprint": evidence["context"]["source_fingerprint"],
            "family_validation": "pending",
        },
    }
