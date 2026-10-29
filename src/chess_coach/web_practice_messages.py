"""Describe practice feedback without revealing hidden lines."""


def move_notice(feedback):
    messages = {
        "illegal": "That move is not legal. Try again.",
        "line_match": "Move played; continue from this position.",
        "needs_verification": "This legal move needs verification.",
        "line_completed": "The supplied line is complete.",
        "objective_verified": "The checkmate objective was verified.",
    }
    return messages.get(feedback, "Move recorded.")
