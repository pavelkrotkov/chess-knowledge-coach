"""Select matching supplied public back-rank lines within the shared budget."""

from .related_backrank_budget import take
from .related_backrank_features import features
from .related_fork_lines import bind_lines
from .related_mate_score import match


def candidate_public(item, source, seen, baseline, budget):
    lines = item.get("lines") or [item["line"]]
    matches = _matches(item, source, seen, baseline, budget, lines)
    if not matches:
        return None
    best = min((item for item, _ in matches), key=lambda item: item["order"])
    bind_lines(best, lines, [index for _, index in matches])
    return best


def _matches(item, source, seen, baseline, budget, lines):
    matches = []
    for index, line in enumerate(lines):
        if not take(budget):
            break
        if len(line) > 17 or len(line.split()) not in {1, 3}:
            continue
        found = match(
            item, source, seen, baseline, item["fen"], features(item["fen"], line.split())
        )
        if found is not None:
            matches.append((found, index))
    return matches
