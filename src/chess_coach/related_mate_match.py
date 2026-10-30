"""Match only the same operation, mating timing and king/attacker structure."""

from .related_fork_lines import bind_lines
from .related_mate_features import corpus_features
from .related_mate_public import candidate_public
from .related_mate_score import match


def candidate(candidate, source, seen, baseline):
    if candidate["type"] == "corpus":
        prompt, features = corpus_features(candidate["fen"], candidate["solution"])
        item = match(candidate, source, seen, baseline, prompt, features)
        if item is not None:
            bind_lines(item, [" ".join(candidate["solution"].split()[1:])], [0])
        return item
    if candidate.get("objective") not in {"legal_line", "checkmate"}:
        return None
    return candidate_public(candidate, source, seen, baseline)
