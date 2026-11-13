"""Bind an unfamiliar exercise to a verified created-exposure source."""

from .evidence_review import inspect_evidence
from .material_created_exposure import _eligible, _prepared
from .material_created_exposure_proof import proof
from .related_capture_position import _features
from .related_capture_source import _opening


def source_for_evidence(db, subject, evidence_id):
    generation = db.connection.execute("PRAGMA data_version").fetchone()[0]
    evidence = inspect_evidence(db, evidence_id)
    if not _eligible(evidence):
        raise ValueError("created exposure unavailable")
    prepared = _prepared(db, evidence, subject)
    if prepared is None or proof(*prepared) is None:
        raise ValueError("created exposure unavailable")
    data = _source(db, evidence, prepared)
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != generation:
        raise ValueError("created exposure source changed")
    return data


def _source(db, evidence, prepared):
    record, fact = prepared
    board = record["board"]
    move = board.parse_uci(record["context"]["played_move"])
    after = board.copy()
    after.push(move)
    capture = after.parse_uci(fact["played"]["uci"][1])
    victim = board.piece_at(move.from_square)
    attacker = after.piece_at(capture.from_square)
    if victim is None or attacker is None:
        raise ValueError("created exposure roles unavailable")
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence["id"],),
    ).fetchone()
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "lines": [" ".join(fact["best"]["uci"])],
        "features": _features(board, move, victim, attacker),
        "opening": _opening(db, record["position_id"]),
        "provenance": {
            "position_id": record["position_id"],
            "evidence_id": evidence["id"],
            "source_fingerprint": record["source_marker"],
            "review_status": evidence["review_status"],
            "review_event_id": review["id"] if review else None,
        },
    }
