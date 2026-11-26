"""Inspect all supported knight-fork roots before considering the played move."""

from .fork_game_root_detail import append_root, finish_details, observe, start_details
from .fork_game_scope import roots, supported
from .fork_proof import _replies, fork_proof
from .fork_targets import targets

# Bump when candidate scope, proof semantics, or outcome policy changes.
VERSION = "knight-fork-game-v2"


class Deadline(Exception):
    """The turn's cooperative proof budget expired."""


def _scan(board, moves, check, observations=None):
    proved, unresolved = set(), False
    for move in moves:
        check()
        shape = targets(board, move)
        check()
        if shape is None:
            observe(observations, move, None, "outside")
            continue
        if _capture_refutation(shape[0], move.to_square):
            check()
            observe(observations, move, None, "outside")
            continue
        proof = fork_proof(board, move, check=check)
        check()
        if proof:
            proved.add(move.uci())
        else:
            unresolved = True
        observe(observations, move, proof, "proved" if proof else "unknown")
    return proved, unresolved


def _capture_refutation(after, square):
    replies = _replies(after)
    if replies is None:
        return None
    return next(
        (reply.uci() for reply in replies if reply.to_square == square and after.is_capture(reply)),
        None,
    )


def _classify(board, played, check, details, observations):
    check()
    if not supported(board):
        return "unknown", "unsupported_position"
    moves = roots(board)
    if details is not None:
        details["total"] = len(moves)
    check()
    proved, unresolved = _scan(board, moves, check, observations)
    check()
    if not proved:
        return ("unresolved", "unresolved_roots") if unresolved else ("no_candidate", None)
    return ("played" if played in proved else "awaiting"), (
        "unresolved_roots" if unresolved else None
    )


def classify(board, played, deadline, clock, *, details=None):
    def check():
        if clock() >= deadline:
            raise Deadline()

    start_details(details, board, played)
    observations = [] if details is not None else None
    try:
        return _classify(board, played, check, details, observations)
    except Deadline:
        return "unknown", "deadline"
    finally:
        if observations is not None:
            for move, proof, state in observations:
                append_root(details, move, proof, state)
        finish_details(details)
