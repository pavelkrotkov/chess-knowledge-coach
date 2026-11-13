"""Prove a played defense against an independently witnessed material discovery."""

import time

from .discovery_geometry import discoveries
from .discovery_mate_success_scope import unclear_after, unsupported
from .discovery_material_success_probe import candidates
from .discovery_material_success_witness import witness
from .material_ambiguity import ambiguous
from .objective_defense_judge import judge

SECONDS = 1.0


def observe(board, played, *, started=None):
    started = time.monotonic() if started is None else started

    def check():
        if time.monotonic() - started >= SECONDS:
            raise TimeoutError

    try:
        return _observe(board, played, started, check)
    except TimeoutError:
        return ambiguous("discovery_material_success", "proof_deadline_exhausted")


def _observe(board, played, started, check):
    if unsupported(board):
        return ambiguous("discovery_material_success", "history_or_position_unavailable")
    try:
        actual = board.parse_uci(played)
    except (ValueError, TypeError):
        return ambiguous("discovery_material_success", "played_move_unavailable")
    nominated, reason = _nominate(board, actual, check)
    if reason:
        return ambiguous("discovery_material_success", reason)
    if not nominated:
        return None
    answer = judge(board.copy(), actual, time.monotonic, started, SECONDS, {})
    if answer["status"] != "correct":
        reason = answer.get("reason", "immediate_mate_unresolved")
        return ambiguous(
            "discovery_material_success",
            "proof_deadline_exhausted" if reason == "timeout" else reason,
        )
    anchor, reason = witness(board, actual, nominated, check)
    if not anchor:
        return ambiguous("discovery_material_success", reason)
    check()
    return {
        "kind": "discovery_material_success",
        "outcome": "success",
        "played": {"move": actual.uci(), "san": board.san(actual)},
        "witness": anchor,
        "threat": anchor["proof"],
        "target_origin": anchor["target_origin"],
        "defense": {
            "move": actual.uci(),
            "san": board.san(actual),
            "legal_replies": answer["legal_replies"],
        },
        "boundary": "The distinct legal alternative permits the proved discovered capture. The played move stops that named discovery, leaves the same piece without an immediate legal capture, and avoids immediate mate. Other threats, later play and intent remain unknown.",
    }


# The opponent-turn probe supplies geometry only. A witness must later prove
# the consequence from the actual legal history before publication.
def _nominate(board, actual, check):
    if actual.promotion or board.is_castling(actual) or unclear_after(board, actual):
        return None, "played_history_or_move_unsupported"
    check()
    nominated = candidates(board, check)
    if nominated is None:
        return None, "nomination_limit_or_unavailable"
    return _filter(board, actual, nominated, check)


def _filter(board, actual, nominated, check):
    if not nominated:
        return [], None
    after = board.copy()
    after.push(actual)
    if after.ep_square is not None:
        return None, "played_history_or_move_unsupported"
    captures = {reply.to_square for reply in after.legal_moves if after.is_capture(reply)}
    safe = []
    for item in nominated:
        check()
        if _safe(board, after, actual, item, captures):
            safe.append(item)
    return (safe, None) if safe else (None, "played_target_or_line_unresolved")


# Keep the physical target through the played move and reject any legal
# immediate capture. Special moves with ambiguous target identity are excluded.
def _safe(board, after, move, candidate, captures):
    origin = candidate["target"]
    target = move.to_square if move.from_square == origin else origin
    if after.piece_at(target) != board.piece_at(origin) or target in captures:
        return False
    return _stops(after, candidate, target)


def _stops(board, candidate, target):
    try:
        attack = board.parse_uci(candidate["move"])
    except ValueError:
        return True
    return not any(
        item["slider"] == candidate["slider"] and item["target"] == target
        for item in discoveries(board, attack)
    )
