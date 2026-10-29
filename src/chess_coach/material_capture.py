"""Evaluate a direct capture using bounded exchange and continuation evidence."""

import chess

from .material_ambiguity import ambiguous
from .material_capture_gain import capture_gain
from .material_capture_rules import conflict
from .material_lines import continuation


def capture_observation(board, candidate, actual, best_line, played_line):
    target = board.piece_at(candidate.to_square)
    gain, reason, check_proof = capture_gain(board, candidate, target)
    if reason:
        return ambiguous("material_capture", reason)
    played_pv, best_pv, reason = _lines(board, candidate, actual, best_line, played_line)
    if reason:
        return ambiguous("material_capture", reason)
    reason = conflict(board, candidate, actual, best_line, played_line, best_pv, played_pv)
    if reason:
        return ambiguous("material_capture", reason)
    return {
        "kind": "material_capture",
        "outcome": "success" if actual == candidate else "failure",
        "target": chess.square_name(candidate.to_square),
        "target_piece": chess.piece_name(target.piece_type),
        "exchange_gain": gain,
        "checking_reply_proof": check_proof,
        "best": best_pv,
        "played": played_pv,
        "boundary": (
            "all legal check evasions and recorded short engine lines only"
            if check_proof
            else "bounded legal immediate replies and recorded short engine lines only"
        ),
    }


def _lines(board, candidate, actual, best_line, played_line):
    if actual != candidate and board.gives_check(actual):
        return None, None, "checking_alternative_unresolved"
    played_pv = continuation(board, played_line, actual.uci(), allow_checks=True)
    best_pv = continuation(board, best_line, allow_checks=board.gives_check(candidate))
    if played_pv is None or (actual != candidate and best_pv is None):
        return None, None, "continuation_unavailable"
    return played_pv, best_pv, None
