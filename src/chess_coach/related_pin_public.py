"""Apply the existing public direct-prompt limits before pin proof."""

from .public_training_line import PUBLIC_LINE_PLIES_LIMIT


def lines(item):
    candidates = item.get("lines") or [item["line"]]
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 16:
        raise ValueError("invalid public solution lines")
    if any(
        not isinstance(line, str) or not 1 <= len(line.split()) <= PUBLIC_LINE_PLIES_LIMIT
        for line in candidates
    ):
        raise ValueError("invalid public solution lines")
    return candidates
