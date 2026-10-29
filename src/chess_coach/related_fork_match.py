"""Score compatible fork roles and geometry using shared context ranking."""

from .related_capture_match import _scored
from .related_capture_position import compatible, prompt_key
from .related_fork_features import corpus_fork_features, fork_features
from .related_fork_lines import bind_lines


def candidate(candidate, source, seen, baseline):
    if candidate["type"] == "corpus":
        prompt, features = corpus_fork_features(candidate["fen"], candidate["solution"])
        item = _scored_match(candidate, source, seen, baseline, prompt, features)
        if item is not None:
            lines = [" ".join(candidate["solution"].split()[1:])]
            bind_lines(item, lines, [0])
        return item
    return _public_candidate(candidate, source, seen, baseline)


def _public_candidate(candidate, source, seen, baseline):
    prompt = candidate["fen"]
    lines = candidate.get("lines") or [candidate["line"]]
    matches = []
    for index, line in enumerate(lines):
        item = _scored_match(
            candidate, source, seen, baseline, prompt, fork_features(prompt, line.split())
        )
        if item is not None:
            matches.append((item, index))
    if not matches:
        return None
    best = min((item for item, _ in matches), key=lambda item: item["order"])
    bind_lines(best, lines, [index for _, index in matches])
    return best


def _scored_match(candidate, source, seen, baseline, prompt, features):
    if not prompt or not compatible(source, features):
        return None
    key = prompt_key(prompt)
    if key in seen:
        return None
    return _scored(candidate, source, features, prompt, key, baseline)
