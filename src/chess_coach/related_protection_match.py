"""Match only legal supplied defenses against the same material role."""

from .puzzle_session_validate import validate_line
from .related_capture_match import _scored
from .related_capture_position import prompt_key
from .related_fork_lines import bind_lines
from .related_protection_features import protection_features, same_mechanism


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
        if budget["checked"] >= budget["limit"]:
            budget["truncated"] = True
            break
        budget["checked"] += 1
        features = protection_features(prompt, line.split())
        if same_mechanism(source, features):
            match = _scored(item, source, features, prompt, key, baseline)
            match["objective_target"] = features["target_square"]
            match["protection_mechanism"] = features["mechanism"]
            matches.append((match, index))
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
