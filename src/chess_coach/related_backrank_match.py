"""Match legal back-rank witnesses within one shared line-check budget."""

from .puzzle_session_validate import validate_line
from .related_backrank_budget import take
from .related_backrank_features import features
from .related_backrank_public import candidate_public
from .related_fork_lines import bind_lines
from .related_mate_score import match


def scorer(budget):
    def candidate(item, source, seen, baseline):
        if item["type"] == "corpus":
            return _corpus(item, source, seen, baseline, budget)
        if item.get("objective") not in {"legal_line", "checkmate"}:
            return None
        return candidate_public(item, source, seen, baseline, budget)

    return candidate


def _corpus(item, source, seen, baseline, budget):
    if not take(budget):
        return None
    try:
        if len(item["solution"]) > 24 or len(item["solution"].split()) not in {2, 4}:
            return None
        prompt = validate_line(item["fen"], item["solution"])
        line = item["solution"].split()[1:]
        found = match(item, source, seen, baseline, prompt, features(prompt, line))
    except (ValueError, TypeError):
        return None
    if found is not None:
        bind_lines(found, [" ".join(line)], [0])
    return found
