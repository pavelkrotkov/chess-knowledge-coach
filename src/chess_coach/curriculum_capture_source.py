"""Resolve the recurring source into one exact owned capture candidate."""

import chess

from .fact_fingerprint import canonical, digest
from .objective_capture_contract import TARGET_VERSION
from .objective_capture_source import resolve
from .plan_capture_action import recommendation
from .unified_source_current import snapshot_hash
from .unified_sources import resolve_source


def read(db, subject, corpus, check):
    report = recommendation(db, subject, corpus, check=check)
    if not report:
        return None, "no_source", None
    source = report["source"]
    resolve_source(db, "own-game", source["version"], source["key"], subject=subject, check=check)
    check()
    history = report["history"]
    if history.get("status") in {"stale", "pending", "incomplete"}:
        return None, "history_unavailable", report
    key = str(source["evidence_id"])
    snapshot = resolve(db, TARGET_VERSION, key, subject, check=check)
    check()
    return _candidate(report, snapshot, key), "available", report


def _candidate(report, snapshot, key):
    board = chess.Board(snapshot["prompt_fen"])
    target = snapshot["provenance"]["objective_target"]
    piece = board.piece_at(chess.parse_square(target))
    if piece is None or snapshot["objective"] != "capture_named_target":
        raise ValueError("capture target unavailable")
    source = report["source"]
    review = snapshot["provenance"]["review_status"]
    scope = "bounded recent source checks" + (
        "; more records may exist" if report["limited"] else ""
    )
    reason = (
        f"Provisional diagnostic from {source['games']} independent games ({scope}); "
        f"source review: {review}. This does not establish mastery."
    )
    return {
        "kind": "new",
        "item_id": None,
        "due": None,
        "source_type": "own-game",
        "source_version": TARGET_VERSION,
        "source_key": key,
        "source_evidence_id": source["evidence_id"],
        "source_review": review,
        "independent_games": source["games"],
        "prompt_fen": snapshot["prompt_fen"],
        "prompt_key": " ".join(board.fen(en_passant="fen").split()[:4]),
        "skill": "hanging_piece",
        "operation": "execute",
        "objective": f"Capture the {chess.piece_name(piece.piece_type)} on {target}.",
        "reason": reason,
        "unified_training": True,
        "binding": digest(canonical([key, snapshot_hash(snapshot), report["history"]])),
    }


def practice_reason(qualified):
    return "Dated capture opportunity importance is unknown. " + (
        "Comparable verified practice selected the previously unmet capture."
        if qualified
        else "Comparable practice priority is unknown or tied; source order is retained."
    )
