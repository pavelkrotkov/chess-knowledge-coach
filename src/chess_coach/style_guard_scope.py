"""Apply existing history, move and other-threat protection boundaries."""

from .material_defense_safety import new_other_threat, safe_defense_move
from .material_threats import threats
from .objective_capture_scope import reason as scope_reason
from .objective_protection_before import probe
from .objective_protection_other import reason as other_reason
from .objective_protection_piece import same_piece


def prepare(board, move, target, clock, start, seconds, check):
    """Preserve the original named target and every existing safety boundary."""
    issue = scope_reason(board, move, clock, start, seconds)
    if issue:
        return None, issue
    before = probe(board, check=lambda _: check())
    check()
    if before is None or set(before["targets"]) != {target}:
        return None, "original_threat_unavailable"
    named = before["targets"][target]
    if len(named) != 1 or not safe_defense_move(board, move, before):
        return None, "original_or_response_unavailable"
    after = board.copy(stack=True)
    after.push(move)
    square = move.to_square if move.from_square == target else target
    if not same_piece(board, after, board.piece_at(target), square):
        return None, "protected_piece_unavailable"
    issue = _following(after, square, before, check)
    return (after, square, named[0]), issue


def _following(after, square, before, check):
    """Other unresolved threats stay unknown even when the named target is recapturable."""
    issue = other_reason(after, list(after.legal_moves), square)
    if issue:
        return issue
    # The named target may be recapturable; uncertainty on any other target still blocks the claim.
    following = threats(after, hypothetical=False, check=lambda _: check(), exclude_target=square)
    if following is None or any(key != square for key in following["uncertain"]):
        return "other_attack_unresolved"
    if new_other_threat(before, following, square):
        return "other_material_threat"
    return None
