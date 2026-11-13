"""Classify the checked named-piece capture on the played child board."""

from .material_threats import threats
from .objective_protection_piece import same_piece
from .objective_protection_refute import witness


def classify(board, move, target, check):
    before = threats(board, hypothetical=True, check=check)
    if before is None or before["targets"] or before["uncertain"]:
        return {"status": "unresolved", "reason": "original_position_unresolved"}
    piece = board.piece_at(target)
    after = board.copy(stack=True)
    after.push(move)
    square = move.to_square if move.from_square == target else target
    if not same_piece(board, after, piece, square):
        return {"status": "unresolved", "reason": "named_piece_unavailable"}
    return _following(after, square, check)


def _following(board, target, check):
    following = threats(board, hypothetical=False, check=check)
    if following is None or following["uncertain"]:
        return {"status": "unresolved", "reason": "unresolved_attack"}
    if set(following["targets"]) - {target}:
        return {"status": "unresolved", "reason": "other_material_threat"}
    attacks = following["targets"].get(target, [])
    for text in sorted(attacks):
        check(0)
        reply = witness(board, [text])
        check(0)
        if reply:
            return {"status": "incorrect", "reason": "profitable_capture", "capture_reply": reply}
    if attacks:
        return {"status": "unresolved", "reason": "capture_unresolved"}
    return {"status": "correct", "reason": "no_profitable_immediate_capture"}
