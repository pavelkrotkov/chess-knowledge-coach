"""Evaluate a direct capture using bounded exchange and continuation evidence."""

import chess

from .material_ambiguity import ambiguous
from .material_capture_gain import capture_gain
from .material_capture_rules import conflict
from .material_lines import continuation


def capture_observation(board, candidate, actual, best_line, played_line):
    target = board.piece_at(candidate.to_square)
    gain, reason = capture_gain(board, candidate, target)
    if reason:
        return ambiguous("material_capture", reason)
    best_pv = continuation(board, best_line)
    played_pv = continuation(board, played_line, actual.uci())
    if best_pv is None or played_pv is None:
        return ambiguous("material_capture", "continuation_unavailable")
    reason = conflict(board, candidate, actual, best_line, played_line, best_pv, played_pv)
    if reason:
        return ambiguous("material_capture", reason)
    return {
        "kind": "material_capture",
        "outcome": "success" if actual == candidate else "failure",
        "target": chess.square_name(candidate.to_square),
        "target_piece": chess.piece_name(target.piece_type),
        "exchange_gain": gain,
        "best": best_pv,
        "played": played_pv,
        "boundary": "legal recaptures on target square and recorded short engine lines only",
    }
