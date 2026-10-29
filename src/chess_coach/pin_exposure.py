"""Assess a pinned-piece move against a verified capture defense."""

from .pin_capture_defense import capture_defenses
from .pin_existing import existing
from .pin_exposure_geometry import exposed


def observe(board, actual):
    candidates = existing(board)
    if not candidates:
        return None
    if len(candidates) != 1:
        return {
            "kind": candidates[0][1]["type"],
            "outcome": "ambiguous",
            "reason": "multiple_pins_unresolved",
        }
    loss = exposed(board, actual, candidates)
    defenses = capture_defenses(board, candidates)
    if loss:
        if not defenses:
            return {
                "kind": loss["type"],
                "outcome": "ambiguous",
                "reason": "alternative_defense_unverified",
                "proof": loss,
                "trigger": {"move": actual.uci(), "san": board.san(actual)},
            }
        return {
            "kind": loss["type"],
            "outcome": "failure",
            "proof": loss,
            "alternative": defenses[0],
            "trigger": {"move": actual.uci(), "san": board.san(actual)},
        }
    success = _success(board, actual, candidates, defenses)
    if success:
        return success
    if any(actual.from_square == pin["pinned"] for _, pin in candidates):
        return {
            "kind": candidates[0][1]["type"],
            "outcome": "ambiguous",
            "reason": "exposure_or_defense_unresolved",
        }
    return None


def _success(board, actual, candidates, defenses):
    if not any(defense["move"] == actual.uci() for defense in defenses):
        return None
    for move in list(board.legal_moves)[:64]:
        loss = exposed(board, move, candidates)
        if loss:
            trigger = {"move": move.uci(), "san": board.san(move)}
            return {
                "kind": loss["type"],
                "outcome": "success",
                "proof": loss,
                "alternative": trigger,
                "trigger": trigger,
            }
    return None
