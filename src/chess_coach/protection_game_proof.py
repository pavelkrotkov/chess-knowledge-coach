"""Choice-independent, bounded protection observations for owned game turns."""

from .protection_game_before import before, status

VERSION = "protection-game-proof-v1"
ROOT_LIMIT = 16


def _contrast(board, target, deadline, clock):
    moves = sorted(board.legal_moves, key=lambda move: move.uci())
    found = set()
    for move in moves[:ROOT_LIMIT]:
        if clock() >= deadline:
            return None
        found.add(status(board, move, target, deadline, clock))
        if {"correct", "incorrect"} <= found:
            return True
    return None if clock() >= deadline else False


def classify(board, played, deadline, clock):
    """Qualify a played move only after a pre-move protective and losing contrast."""
    initial, reason = before(board, deadline, clock)
    if reason:
        return "unknown", reason
    if initial is None:
        return "no_opportunity", None
    target = next(iter(initial["targets"]))
    contrast = _contrast(board, target, deadline, clock)
    if contrast is not True:
        return "unknown", "contrast_unresolved" if contrast is False else "deadline"
    if clock() >= deadline:
        return "opportunity_unresolved", "deadline"
    try:
        move = board.parse_uci(played)
    except ValueError:
        return "opportunity_unresolved", "played_unavailable"
    played_status = status(board, move, target, deadline, clock)
    if clock() >= deadline:
        return "opportunity_unresolved", "deadline"
    return {
        "correct": ("protected", None),
        "incorrect": ("missed", None),
    }.get(played_status, ("opportunity_unresolved", "played_unresolved"))
