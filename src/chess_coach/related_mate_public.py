"""Select only matching supplied public mate lines."""

from .related_fork_lines import bind_lines
from .related_mate_features import mate_features
from .related_mate_score import match


def candidate_public(candidate, source, seen, baseline):
    lines = candidate.get("lines") or [candidate["line"]]
    matches = []
    for index, line in enumerate(lines):
        item = match(
            candidate,
            source,
            seen,
            baseline,
            candidate["fen"],
            mate_features(candidate["fen"], line.split()),
        )
        if item is not None:
            matches.append((item, index))
    if not matches:
        return None
    best = min((item for item, _ in matches), key=lambda item: item["order"])
    bind_lines(best, lines, [index for _, index in matches])
    return best
