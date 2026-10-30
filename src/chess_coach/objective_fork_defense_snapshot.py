"""Bind a verified pre-existing fork anchor to an owned defense objective."""

import chess

from .fork_defense_probe import hypothetical
from .material_opportunity_source import load_source
from .objective_contract import OWNED_HISTORY
from .objective_fork_defense_contract import GOAL, OBJECTIVE
from .related_fork_prevention_source_witness import branch


def snapshot(db, board, evidence, fact):
    payload = fact["payload"]
    proof, anchored, defense = branch(board, payload)
    before = hypothetical(board)
    if before is None or before.get(proof["move"]) != [
        chess.parse_square(s) for s in proof["targets"]
    ]:
        raise ValueError("pre-existing fork unavailable")
    source = load_source(db, fact["detector_run_id"])
    review = db.connection.execute(
        "SELECT id FROM evidence_review_events WHERE evidence_id=? ORDER BY id DESC LIMIT 1",
        (evidence["id"],),
    ).fetchone()
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": GOAL,
        "lines": [defense.uci()],
        "provenance": {
            "source_fingerprint": source["source_marker"],
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "review_status": evidence["review_status"],
            "review_event_id": review["id"] if review else None,
            "mapping_run_id": evidence["mapping_run_id"],
            "mapper_version": evidence["mapper_version"],
            "fact_id": fact["id"],
            "detector_run_id": fact["detector_run_id"],
            "objective_version": OBJECTIVE,
            "history_mode": OWNED_HISTORY,
            "threat_origin": "positional_before_played",
            "anchor_move": anchored.peek().uci(),
            "fork_certificate": proof,
            "fork_attacker": chess.square_name(chess.Move.from_uci(proof["move"]).from_square),
            "fork_targets": proof["targets"],
            "source_outcome": evidence["outcome"],
        },
    }
