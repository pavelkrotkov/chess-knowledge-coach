"""Verify that the proposed alternative actually protects the identified piece."""

from .material_threats import threats


def best_protects(board, candidate, best_pv):
    before = candidate["before"]["targets"]
    original = next(iter(before)) if before else candidate["move"].from_square
    original_piece = board.piece_at(original)
    move = _quiet_move(board, best_pv)
    if move is None:
        return False
    after = board.copy()
    after.push(move)
    square = move.to_square if move.from_square == original else original
    if after.piece_at(square) != original_piece or original_piece is None:
        return False
    return _safe_target(after, square)


def _quiet_move(board, best_pv):
    try:
        move = board.parse_uci(best_pv["uci"][0])
    except (ValueError, IndexError):
        return None
    return (
        move
        if move in board.legal_moves and not board.is_capture(move) and not board.gives_check(move)
        else None
    )


def _safe_target(board, square):
    probe = threats(board, hypothetical=False)
    return probe is not None and not probe["ambiguous"] and square not in probe["targets"]
