"""Verify an existing named pin using the qualified exposure and capture kernel."""

import chess

from .pin_capture_defense import capture_defenses
from .pin_existing import existing
from .pin_exposure_geometry import exposed


def judge(board, move, named):
    candidates = existing(board)
    if len(candidates) != 1 or not _matches(candidates[0], named):
        return "unresolved", "named_existing_pin_unavailable", None
    defenses = capture_defenses(board, candidates)
    if any(item["move"] == move.uci() for item in defenses):
        return "correct", "named_pinner_capture_proved", None
    loss = exposed(board, move, candidates)
    if loss:
        return "incorrect", "named_pin_exposure_proved", loss
    return "unresolved", "pin_defense_unresolved", None


def _matches(candidate, named):
    attacker, pin = candidate
    return (
        chess.square_name(attacker) == named["attacker"]
        and chess.square_name(pin["pinned"]) == named["pinned"]
        and chess.square_name(pin["rear"]) == named["rear"]
        and pin["type"] == named["kind"]
    )
