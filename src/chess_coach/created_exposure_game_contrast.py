"""Nominate and prove a bounded, choice-independent exposure contrast."""

from .objective_created_judge import judge
from .pawn_scope import history_known
from .related_created_proof import nominations

ROOT_LIMIT = 12


def status(board, move, target, deadline, clock):
    start = clock()
    if start >= deadline:
        return {"status": "unresolved", "reason": "deadline"}
    return judge(board, move, target, clock, start, deadline - start, {})


def _loss(board, candidates, target, deadline, clock):
    return any(
        bad.from_square == target
        and (result := status(board, bad, target, deadline, clock)).get("status") == "incorrect"
        and result.get("capture_reply") == capture.uci()
        for bad, capture in candidates[:ROOT_LIMIT]
    )


def _safe(board, target, deadline, clock):
    moves = sorted(board.legal_moves, key=lambda item: item.uci())[:ROOT_LIMIT]
    return any(
        status(board, move, target, deadline, clock).get("status") == "correct" for move in moves
    )


def _proved(board, candidates, target, deadline, clock):
    return (
        _loss(board, candidates, target, deadline, clock)
        and _safe(board, target, deadline, clock)
        and clock() < deadline
    )


# Nomination happens before the played move is considered. Multiple possible
# physical pieces are ambiguous even if one could be proved by the search.
def contrast(board, profile, deadline, clock):
    if not history_known(board):
        return None, "history_unavailable"
    candidates = nominations(board, None, profile)
    if clock() >= deadline:
        return None, "deadline"
    if not candidates:
        return None, "no_sampled_nominee"
    target = candidates[0][0].from_square
    if any(move.from_square != target for move, _ in candidates):
        return None, "ambiguous_target"
    if _proved(board, candidates, target, deadline, clock):
        return target, None
    return None, "deadline" if clock() >= deadline else "contrast_unresolved"
