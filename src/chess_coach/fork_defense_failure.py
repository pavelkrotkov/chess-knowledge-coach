"""Verify an engine continuation and a distinct legal defensive alternative."""

import chess

from .fork_defense_comparison import failed
from .fork_defense_safety import safe_best
from .material_ambiguity import ambiguous


def failure(board, actual, best_line, played_line, candidates, following):
    best = safe_best(board, best_line)
    if best is None:
        return ambiguous("fork_defense", "alternative_defense_unverified")
    proof = _recorded_fork(played_line, following)
    if proof is None:
        return ambiguous("fork_defense", "recorded_fork_unverified")
    lines, reason = failed(board, actual, best, played_line, best_line, proof)
    if not lines:
        return ambiguous("fork_defense", reason)
    return {
        "kind": "fork_defense",
        "outcome": "failure",
        "threats": [],
        "fork": proof,
        "threat_origin": _origin(proof, candidates),
        **lines,
        "boundary": "recorded engine continuation rooted at the played move and bounded immediate defenses; not actual subsequent game moves",
    }


def _recorded_fork(played_line, following):
    pv = played_line.get("pv") if isinstance(played_line, dict) else None
    moves = pv.split() if isinstance(pv, str) else []
    return following["proven"].get(moves[1]) if len(moves) >= 2 else None


def _origin(proof, candidates):
    squares = candidates.get(proof["move"])
    if (
        squares is not None
        and [chess.square_name(square) for square in squares] == proof["targets"]
    ):
        return "positional_before_played"
    return "created_by_played_move"
