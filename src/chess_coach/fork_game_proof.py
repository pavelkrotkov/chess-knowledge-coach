"""Inspect all supported knight-fork roots before considering the played move."""

from .fork_game_scope import roots, supported
from .fork_proof import _replies, fork_proof
from .fork_targets import targets

# Bump when candidate scope, proof semantics, or outcome policy changes.
VERSION = "knight-fork-game-v2"


class Deadline(Exception):
    """The turn's cooperative proof budget expired."""


def _scan(board, moves, check):
    proved, unresolved = set(), False
    for move in moves:
        check()
        shape = targets(board, move)
        check()
        if shape is None:
            continue
        if _capture_refutation(shape[0], move.to_square):
            check()
            continue
        proof = fork_proof(board, move, check=check)
        check()
        if proof:
            proved.add(move.uci())
        else:
            unresolved = True
    return proved, unresolved


def _capture_refutation(after, square):
    replies = _replies(after)
    if replies is None:
        return None
    return next(
        (reply.uci() for reply in replies if reply.to_square == square and after.is_capture(reply)),
        None,
    )


def classify(board, played, deadline, clock):
    def check():
        if clock() >= deadline:
            raise Deadline()

    try:
        check()
        if not supported(board):
            return "unknown", "unsupported_position"
        moves = roots(board)
        check()
        proved, unresolved = _scan(board, moves, check)
        check()
    except Deadline:
        return "unknown", "deadline"
    if not proved:
        return ("unresolved", "unresolved_roots") if unresolved else ("no_candidate", None)
    return ("played" if played in proved else "awaiting"), (
        "unresolved_roots" if unresolved else None
    )
