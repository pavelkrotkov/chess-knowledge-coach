"""Find a single unambiguous target for an immediate protection observation."""

from .material_ambiguity import ambiguous
from .material_defense_rules import before_reason, target
from .material_threats import threats


def candidate(board, played):
    before = threats(board, hypothetical=True)
    reason = before_reason(before)
    if reason:
        return ambiguous("material_protection", reason)
    try:
        move = board.parse_uci(played)
    except ValueError:
        return ambiguous("material_protection", "invalid_played_move")
    if move not in board.legal_moves or board.is_capture(move) or board.gives_check(move):
        return (
            ambiguous("material_protection", "checking_or_capturing_defense")
            if before["targets"]
            else None
        )
    return _after_candidate(board, move, before)


def _after_candidate(board, move, before):
    after = board.copy()
    after.push(move)
    following = threats(after, hypothetical=False)
    if following is None or following["ambiguous"]:
        return (
            ambiguous("material_protection", "post_move_attack_unresolved")
            if before["targets"]
            else None
        )
    square = target(before, following, move)
    return (
        {"move": move, "target": square, "before": before, "following": following}
        if square is not None
        else None
    )
