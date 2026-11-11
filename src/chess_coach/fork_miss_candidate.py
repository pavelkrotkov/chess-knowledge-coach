"""Compare only a measured best root in the independent knight scope."""

from .fork_comparison import miss
from .fork_game_scope import roots, supported
from .fork_proof import fork_proof
from .fork_targets import targets, unsupported_shape


def _uncertain_played(board, actual, moves):
    return bool(unsupported_shape(board, actual) or (actual in moves and targets(board, actual)))


def candidate(board, actual, best, source, check):
    moves = roots(board)
    if _uncertain_played(board, actual, moves):
        return "unresolved"
    if not supported(board) or best not in moves or targets(board, best) is None:
        return "unresolved"
    proof = fork_proof(board, best, check=check)
    check()
    if not proof:
        return "unresolved"
    result = miss(board, actual, best, source["best"], source["played"], proof)
    return "miss" if result["outcome"] == "failure" else "unresolved"
