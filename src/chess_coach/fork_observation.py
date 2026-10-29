"""Describe a bounded fork in the played or best current continuation."""

import chess

from .fork_comparison import miss
from .fork_proof import fork_proof
from .fork_result import ambiguous
from .fork_targets import targets
from .material_lines import continuation
from .material_observation_fallback import _best_move


def observe(board, played, best_line, played_line):
    try:
        actual = chess.Move.from_uci(played)
    except ValueError:
        return ambiguous("invalid_played_move")
    if actual not in board.legal_moves:
        return ambiguous("invalid_played_move")
    played_proof = fork_proof(board, actual)
    if played_proof:
        return _success(board, actual, played_line, played_proof)
    return _alternative(board, actual, best_line, played_line)


def _alternative(board, actual, best_line, played_line):
    best = _best_move(board, best_line)
    if not isinstance(best, chess.Move):
        return ambiguous("current_best_unavailable")
    best_proof = fork_proof(board, best)
    if best_proof is None:
        return (
            ambiguous("fork_unresolved") if targets(board, best) or targets(board, actual) else None
        )
    return miss(board, actual, best, best_line, played_line, best_proof)


def _success(board, actual, played_line, proof):
    played = continuation(board, played_line, actual.uci(), allow_checks=True)
    if played is None:
        return ambiguous("continuation_unavailable")
    return {"kind": "fork", "outcome": "success", "proof": proof, "played": played, "best": None}
