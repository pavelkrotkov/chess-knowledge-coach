"""Classify one played move only after a proved pre-move contrast."""

import chess

from .created_exposure_game_contrast import contrast, status
from .related_created_proof import nominations

VERSION = "created-exposure-game-proof-v2"


def _matches(board, move, result, profile):
    capture = result.get("capture_reply")
    if not isinstance(capture, str):
        return False
    return (move, chess.Move.from_uci(capture)) in nominations(board, None, profile)


def _played(board, played, target, profile, deadline, clock):
    try:
        move = board.parse_uci(played)
    except ValueError:
        return "opportunity_unresolved", "played_unavailable"
    result = status(board, move, target, deadline, clock)
    if clock() >= deadline:
        return "opportunity_unresolved", "deadline"
    if result.get("status") == "correct":
        return "protected", None
    if (
        move.from_square == target
        and result.get("status") == "incorrect"
        and _matches(board, move, result, profile)
        and clock() < deadline
    ):
        return "missed", None
    return "opportunity_unresolved", "played_unresolved"


def classify(board, played, profile, deadline, clock):
    """Fix and prove the profile contrast without consulting the played move."""
    if not board.is_valid():
        return "unknown", "history_unavailable"
    target, reason = contrast(board, profile, deadline, clock)
    if reason:
        return "unknown", reason
    if clock() >= deadline:
        return "opportunity_unresolved", "deadline"
    return _played(board, played, target, profile, deadline, clock)
