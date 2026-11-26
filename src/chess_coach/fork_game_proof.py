"""Inspect all supported knight-fork roots before considering the played move."""

from .fork_game_scope import roots, supported
from .fork_proof import _replies, fork_proof
from .fork_targets import targets

# Bump when candidate scope, proof semantics, or outcome policy changes.
VERSION = "knight-fork-game-v2"


class Deadline(Exception):
    """The turn's cooperative proof budget expired."""


def _scan(board, moves, check, details=None):
    proved, unresolved = set(), False
    for move in moves:
        check()
        shape = targets(board, move)
        check()
        proof = None
        state = "outside"
        if shape is not None and not _capture_refutation(shape[0], move.to_square):
            proof = fork_proof(board, move, check=check)
            check()
            state = "proved" if proof else "unknown"
            if proof:
                proved.add(move.uci())
            else:
                unresolved = True
        if details is not None:
            details["attempted"] += 1
            if len(details["roots"]) < 32:
                details["roots"].append([move.uci(), proof["targets"] if proof else [], state])
        check()
    return proved, unresolved


def _capture_refutation(after, square):
    replies = _replies(after)
    if replies is None:
        return None
    return next(
        (reply.uci() for reply in replies if reply.to_square == square and after.is_capture(reply)),
        None,
    )


def classify(board, played, deadline, clock, *, details=None):
    def check():
        if clock() >= deadline:
            raise Deadline()

    if details is not None:
        details.update(
            side="white" if board.turn else "black",
            played=played,
            total=None,
            attempted=0,
            roots=[],
        )
    try:
        check()
        if not supported(board):
            return "unknown", "unsupported_position"
        moves = roots(board)
        if details is not None:
            details["total"] = len(moves)
        check()
        proved, unresolved = _scan(board, moves, check, details)
        check()
    except Deadline:
        return "unknown", "deadline"
    finally:
        if details is not None:
            total = details["total"]
            details["unsearched"] = None if total is None else total - details["attempted"]
    if not proved:
        return ("unresolved", "unresolved_roots") if unresolved else ("no_candidate", None)
    return ("played" if played in proved else "awaiting"), (
        "unresolved_roots" if unresolved else None
    )
