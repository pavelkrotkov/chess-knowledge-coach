"""Classify a complete immediate attack scan with its legal witness."""

from .objective_capture_proof import unknown
from .objective_protection_refute import witness


def result(board, target, following, replies, clock, start, seconds, base):
    attacks = following["targets"].get(target, [])
    reply = witness(board, attacks) if attacks else None
    if clock() - start > seconds:
        return unknown(base, "timeout")
    if attacks and not reply:
        return unknown(base, "capture_unresolved")
    result = {**base, "legal_replies": sorted(move.uci() for move in replies)}
    if reply:
        return {
            **result,
            "status": "incorrect",
            "reason": "profitable_capture",
            "capture_reply": reply,
        }
    return {**result, "status": "correct", "reason": "no_profitable_immediate_capture"}
