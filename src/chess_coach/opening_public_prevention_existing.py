"""Prove an anchored pre-existing knight fork and a bounded defense."""

from .fork_defense_anchor import anchor
from .opening_public_prevention_created import knights
from .opening_public_prevention_response import alternative, assessment


def pre_existing(board, recorded, before, clock, start, deadline, check, charge, maximum):
    candidates = knights(board, before)
    if not candidates:
        return None, None
    witness = anchor(board, candidates, check=check, on_proof=charge)
    if witness is None:
        return None, "unsupported"
    if "reason" in witness:
        return None, "incomplete"
    response = assessment(board, recorded, clock, start, deadline, check, charge)
    if response is not None:
        return {
            "origin": "pre_existing",
            "anchor": witness,
            "response": response,
            "recorded_response_status": "correct",
        }, None
    choice, reason = alternative(board, recorded, clock, start, deadline, check, charge, maximum)
    if choice is None:
        return None, reason
    move, response = choice
    return {
        "origin": "pre_existing",
        "anchor": witness,
        "response": response,
        "recorded_response_status": "unresolved",
        "alternative_uci": move.uci(),
        "alternative_san": board.san(move),
    }, None
