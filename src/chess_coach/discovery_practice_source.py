"""Resolve and revalidate an owned discovery practice source."""

from .discovery_practice import VERSION
from .evidence_review import inspect_evidence
from .learner_identity import normalize_identity


def resolve(db, version, key, subject):
    if not _valid_key(version, key):
        raise ValueError("discovery practice unavailable")
    evidence = inspect_evidence(db, int(key))
    if evidence["subject"] != normalize_identity(subject) or evidence["review_status"] in {
        "rejected",
        "revoked",
    }:
        raise ValueError("discovery practice unavailable")
    if evidence["discovery_currentness"] != "current" or evidence["outcome"] not in {
        "success",
        "failure",
    }:
        raise ValueError("discovery practice unavailable")
    proof = evidence["discovery_observation"].get("proof")
    if not proof:
        raise ValueError("discovery practice unavailable")
    return _snapshot(db, evidence, proof)


def _snapshot(db, evidence, proof):
    move = proof["move"]
    lines = (
        [move]
        if proof["mate"]
        else [" ".join((move, branch["reply"], branch["capture"])) for branch in proof["branches"]]
    )
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence["id"],),
    ).fetchone()
    import chess

    board = chess.Board(evidence["decision_fen"])
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": "checkmate" if proof["mate"] else "legal_line",
        "lines": lines,
        "provenance": {
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "review_status": evidence["review_status"],
            "review_event_id": review["id"] if review else None,
            "detector_run_id": evidence["facts"][0]["detector_run_id"],
        },
    }


def _valid_key(version, key):
    return version == VERSION and key.isdecimal() and 0 < int(key) < 2**63 and str(int(key)) == key
