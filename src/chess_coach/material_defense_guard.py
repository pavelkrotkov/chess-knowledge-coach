"""Verify that the proposed alternative actually protects the identified piece."""

from .material_defense_safety import new_other_threat, safe_defense_move
from .material_threats import check_options, threats


def best_protects(board, candidate, best_pv, *, check=None):
    before = candidate["before"]["targets"]
    original = next(iter(before)) if before else candidate["move"].from_square
    original_piece = board.piece_at(original)
    move = _defense_move(board, best_pv, candidate["before"], check)
    if move is None:
        return False
    after = board.copy()
    after.push(move)
    square = move.to_square if move.from_square == original else original
    if after.piece_at(square) != original_piece or original_piece is None:
        return False
    return _safe_target(after, square, candidate["before"], check)


def _defense_move(board, best_pv, before, check):
    try:
        move = board.parse_uci(best_pv["uci"][0])
    except (ValueError, IndexError):
        return None
    options = {"check": check} if check is not None else {}
    return move if safe_defense_move(board, move, before, **options) else None


def _safe_target(board, square, before, check):
    options = check_options(check)
    probe = threats(board, hypothetical=False, **options)
    return (
        probe is not None
        and square not in probe["uncertain"]
        and square not in probe["targets"]
        and not new_other_threat(before, probe, square)
    )
