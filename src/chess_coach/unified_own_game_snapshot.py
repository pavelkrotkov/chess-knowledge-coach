"""Make a bounded material witness snapshot without exposing its move."""

import chess

KINDS = {"material_capture", "material_protection"}


def key_for(view):
    objective = view["objective"]
    return "{}:{}:{}".format(view["position_id"], objective["kind"], objective["target"])


def snapshot(view, review, evidence_id):
    board = chess.Board(view["decision_fen"])
    color = "white" if board.turn else "black"
    witness = view["objective_witness"]
    move = chess.Move.from_uci(witness["uci"][0])
    if not board.is_valid() or color != view["learner_color"] or move not in board.legal_moves:
        raise ValueError("invalid material witness")
    target = view["objective"]["target"]
    chess.parse_square(target)
    return {
        "prompt_fen": board.fen(),
        "learner_color": color,
        "objective": view["objective"]["kind"],
        "lines": [move.uci()],
        "provenance": {
            "lineage": view["lineage"],
            "source_fingerprint": view["source_fingerprint"],
            "evidence_id": evidence_id,
            "position_id": view["position_id"],
            "review_event_id": review["id"] if review else None,
            "review_status": view["review_status"],
            "witness_role": witness["role"],
            "objective_target": target,
        },
    }
