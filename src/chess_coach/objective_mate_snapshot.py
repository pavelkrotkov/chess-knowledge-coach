"""Build a single-example snapshot with explicit objective and history mode."""

from .mate_practice_lines import prepared_lines
from .objective_contract import OBJECTIVE, OWNED_HISTORY, UNAVAILABLE
from .pawn_scope import history_known


def snapshot(db, board, evidence, fact, fingerprint):
    lines = [
        line for line in prepared_lines(board, fact["payload"]["proof"]) if len(line.split()) == 1
    ]
    if not lines or board.is_game_over(claim_draw=True):
        raise ValueError("mate-in-one source unavailable")
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence["id"],),
    ).fetchone()
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": "mate_in_one",
        "lines": [sorted(lines)[0]],
        "provenance": {
            "source_fingerprint": fingerprint,
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "review_status": evidence["review_status"],
            "review_event_id": review["id"] if review else None,
            "detector_run_id": fact["detector_run_id"],
            "objective_version": OBJECTIVE,
            "history_mode": OWNED_HISTORY if history_known(board) else UNAVAILABLE,
        },
    }
