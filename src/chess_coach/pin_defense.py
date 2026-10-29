"""Bounded legal alternatives for pin prevention; unresolved searches stay ambiguous."""

import chess

from .fork_defense_safety import quiet_after
from .material_ambiguity import ambiguous
from .material_exchange_rules import unclear
from .pin_defense_choice import failure
from .pin_defense_success import success
from .pin_existing import existing
from .pin_exposure import observe as exposure_observation
from .pin_scan import scan


def observe(board, played, best_line, played_line):
    try:
        actual = chess.Move.from_uci(played)
    except ValueError:
        return None
    if actual not in board.legal_moves:
        return None
    if unclear(board) or board.ep_square is not None:
        return (
            ambiguous("relative_pin", "history_or_position_unresolved") if existing(board) else None
        )
    exposure = exposure_observation(board, actual)
    if exposure is not None:
        return exposure
    after = quiet_after(board, actual)
    if after is None:
        return None
    return _assessment(board, actual, after, best_line, played_line)


def _assessment(board, actual, after, best_line, played_line):
    current = scan(after)
    if current is None:
        return None
    if current["proven"]:
        return failure(board, actual, after, current["proven"][0], best_line, played_line)
    if current["uncertain"]:
        return _uncertain(current["uncertain"][0])
    return success(board, actual, played_line, after)


def _uncertain(pin):
    fact = ambiguous(pin["type"], pin.get("reason", "pin_consequence_unresolved"))
    fact["geometry"] = {
        "move": pin["move"],
        "san": pin["san"],
        "origin": "opponent_candidate",
        "pinned": chess.square_name(pin["pinned"]),
        "rear": chess.square_name(pin["rear"]),
    }
    return fact
