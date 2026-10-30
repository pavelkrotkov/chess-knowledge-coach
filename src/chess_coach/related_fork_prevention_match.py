"""Match supported supplied defenses, preserving their exact line indices."""

from .puzzle_session_validate import validate_line
from .related_capture_match import _scored
from .related_capture_position import prompt_key
from .related_fork_lines import bind_lines
from .related_fork_prevention_features import features


def scorer(budget):
    def candidate(item, source, seen, baseline):
        return _candidate(item, source, seen, baseline, budget)

    return candidate


def _candidate(item, source, seen, baseline, budget):
    try:
        prompt, lines = _prompt(item)
    except (ValueError, TypeError, KeyError):
        return None
    key = prompt_key(prompt)
    if key in seen:
        return None
    matches = []
    for index, line in enumerate(lines):
        found = features(prompt, line.split(), source, budget)
        if found is not None:
            match = _scored(item, source, found, prompt, key, baseline)
            match["defense_role"] = found["defense_role"]
            match["target_roles"] = found["target"]
            matches.append((match, index))
        if budget["truncated"]:
            break
    if not matches:
        return None
    best = min(matches, key=lambda entry: entry[0]["order"])[0]
    bind_lines(best, lines, [index for _, index in matches])
    return best


def _prompt(item):
    if item["type"] == "corpus":
        return validate_line(item["fen"], item["solution"]), [
            " ".join(item["solution"].split()[1:])
        ]
    return item["fen"], item["lines"]
