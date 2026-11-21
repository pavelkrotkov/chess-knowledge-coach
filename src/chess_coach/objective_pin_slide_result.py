"""Classify a supported slide or independently proved rear exposure."""

from .objective_capture_proof import unknown
from .objective_pin_slide_budget import PIN_REVALIDATION, take
from .objective_pin_slide_proof import prove
from .objective_pin_slide_scope import named_pin
from .objective_short_history import history_hash
from .pin_exposure_geometry import exposed


def assess(board, move, named, clock, start, seconds, base):
    result = prove(board, move, named)
    if clock() - start > seconds:
        return unknown(base, "timeout")
    if result is not None:
        return {
            **base,
            "status": "correct",
            "reason": "named_slide_and_recaptures_proved",
            "history_hash": history_hash(board),
            "move": move.uci(),
            "san": board.san(move),
            "recaptures": result,
        }
    candidate = named_pin(board, named)
    take(PIN_REVALIDATION)
    loss = exposed(board, move, [candidate]) if candidate is not None else None
    if clock() - start > seconds:
        return unknown(base, "timeout")
    if loss:
        return {
            **base,
            "status": "incorrect",
            "reason": "named_rear_capture_proved",
            "history_hash": history_hash(board),
            "move": move.uci(),
            "san": board.san(move),
            "proof": loss,
        }
    return unknown(base, "pin_slide_unresolved")
