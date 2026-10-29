"""Assess a concrete pin threat and alternative defenses."""

import chess

from .fork_defense_safety import quiet_after, safe_material
from .material_ambiguity import ambiguous
from .material_lines import continuation
from .material_observation_fallback import _best_move
from .pin_scan import scan


def failure(board, actual, after, witness, best_line, played_line):
    best = _best_move(board, best_line)
    if not isinstance(best, chess.Move) or best == actual:
        return _unresolved(witness, "alternative_defense_unverified")
    alternative = quiet_after(board, best)
    checked = scan(alternative) if alternative else None
    line = continuation(board, best_line, best.uci(), allow_checks=True)
    if not _safe_alternative(checked, alternative):
        return _unresolved(witness, "alternative_defense_unverified")
    if line is None or line["material_delta"] < 0:
        return _unresolved(witness, "compensation_unresolved")
    return {
        "kind": witness["type"],
        "outcome": "failure",
        "proof": witness,
        "alternative": {"move": best.uci(), "san": board.san(best)},
        "best": line,
    }


def _safe_alternative(checked, board):
    return bool(
        checked and not checked["proven"] and not checked["uncertain"] and safe_material(board)
    )


def _unresolved(witness, reason):
    return {**ambiguous(witness["type"], reason), "proof": witness}
