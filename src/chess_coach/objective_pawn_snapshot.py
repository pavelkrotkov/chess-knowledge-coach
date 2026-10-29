"""Bind a source-proved pawn objective to one verified exemplar."""

from .objective_contract import OWNED_HISTORY
from .objective_pawn_bounds import alternative, root_goal, verdict
from .objective_pawn_contract import OBJECTIVE
from .pawn_proof import VERSION as PROOF_VERSION
from .pawn_tables import MANIFEST_SHA256


def snapshot(board, evidence, review):
    fact = evidence["context"]["pawn_observation"]
    proof = fact["proof"]
    goal = root_goal(proof)
    if goal is None or goal != fact["root_wdl"]:
        raise ValueError("pawn objective unavailable")
    moves = sorted(move["uci"] for move in fact["preserving"])
    move = _exemplar(board, proof, goal, moves)
    return {
        "prompt_fen": board.fen(),
        "learner_color": "white" if board.turn else "black",
        "objective": "preserve_pawn_win" if goal == 1 else "preserve_pawn_draw",
        "lines": [move],
        "provenance": {
            "evidence_id": evidence["id"],
            "position_id": evidence["position_id"],
            "review_status": evidence["review_status"],
            "review_event_id": review,
            "source_fingerprint": evidence["context"]["source_fingerprint"],
            "objective_version": OBJECTIVE,
            "history_mode": OWNED_HISTORY,
            "result_goal": goal,
            "proof_version": PROOF_VERSION,
            "proof_manifest_sha256": MANIFEST_SHA256,
        },
    }


def _exemplar(board, proof, goal, moves):
    for text in moves:
        bounds = alternative(proof, text)
        if bounds is not None and verdict(*bounds, goal)[0] == "correct":
            move = board.parse_uci(text)
            if move in board.legal_moves:
                return text
    raise ValueError("pawn exemplar unavailable")
