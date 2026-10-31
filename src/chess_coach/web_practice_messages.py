"""Describe practice feedback without revealing hidden lines."""


def move_notice(feedback, objective=None):
    if feedback == "objective_verified" and objective in {
        "capture_named_target",
        "bounded_material_gain",
    }:
        return "The bounded capture objective was verified."
    messages = {
        "incorrect": "This move does not give checkmate within the announced horizon.",
        "illegal": "That move is not legal. Try again.",
        "line_match": "Move played; continue from this position.",
        "needs_verification": "This legal move needs verification.",
        "line_completed": "The supplied line is complete.",
        "objective_verified": "The checkmate objective was verified.",
    }
    return messages.get(feedback, "Move recorded.")
