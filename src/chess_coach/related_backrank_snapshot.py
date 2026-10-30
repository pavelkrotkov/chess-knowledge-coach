"""Bind a selected proved attack to current source and review lineage."""

from .related_capture_source import _opening


def snapshot(db, board, evidence, fact, fingerprint, root_move, root, lines):
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence["id"],),
    ).fetchone()
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": "mate_in_one" if root["distance_plies"] == 1 else "mate_within_two",
        "lines": lines,
        "opening": _opening(db, evidence["position_id"]),
        "outcome": evidence["outcome"],
        "provenance": {
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "source_fingerprint": fingerprint,
            "review_status": evidence["review_status"],
            "review_event_id": review["id"] if review else None,
            "detector_run_id": fact["detector_run_id"],
            "fact_id": fact["id"],
            "mapping_run_id": evidence["mapping_run_id"],
            "mapper_version": evidence["mapper_version"],
            "operation": evidence["operation"],
            "selected_root": root_move,
            "root_certificate": root,
        },
    }
