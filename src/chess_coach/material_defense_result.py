"""Assess a verified short continuation for one targeted protection probe."""

import chess

from .material_ambiguity import ambiguous


def assess(board, candidate, best_pv, played_pv):
    move = candidate["move"]
    target = candidate["target"]
    before, following = candidate["before"], candidate["following"]
    after = board.copy()
    after.push(move)
    piece = after.piece_at(target)
    if piece is None or piece.color != board.turn:
        return ambiguous("material_protection", "protected_piece_unavailable")
    if target not in following["targets"] and before["targets"]:
        outcome = "success" if played_pv["material_delta"] >= 0 else "ambiguous"
    else:
        outcome = _loss_outcome(target, following, best_pv, played_pv)
    return {
        "kind": "material_protection",
        "outcome": outcome,
        "target": chess.square_name(target),
        "target_piece": chess.piece_name(piece.piece_type),
        "best": best_pv,
        "played": played_pv,
        "boundary": "hypothetical immediate capture probe and recorded short engine lines only",
    }


def _loss_outcome(target, following, best_pv, played_pv):
    reply = chess.Move.from_uci(played_pv["uci"][1])
    if (
        reply.to_square == target
        and reply.uci() in following["targets"].get(target, [])
        and played_pv["material_delta"] <= -3
        and best_pv["material_delta"] >= 0
    ):
        return "failure"
    return "ambiguous"
