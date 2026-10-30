"""Match a legal supplied defense with a particular created-fork counterfactual."""

from .related_capture_match import _scored
from .related_capture_position import prompt_key
from .related_fork_avoidance_candidate_line import candidate_line
from .related_fork_lines import bind_lines
from .related_fork_prevention_match import _prompt


def scorer(budget):
    def candidate(item, source, seen, baseline):
        return _candidate(item, source, seen, baseline, budget)

    return candidate


def _candidate(item, source, seen, baseline, budget):
    try:
        prompt, lines = _prompt(item)
    except (ValueError, TypeError, KeyError):
        budget["unknown"] += 1
        return None
    key = prompt_key(prompt)
    if key in seen:
        return None
    for index, line in enumerate(lines):
        found = candidate_line(prompt, line.split(), source, budget)
        if found is not None:
            created_witness, features = found
            match = _scored(item, source, features, prompt, key, baseline)
            match["created_witness"] = created_witness
            match["defense_role"] = source["defense_role"]
            match["target_roles"] = source["target"]
            bind_lines(match, lines, [index])
            return match
        if budget["truncated"]:
            return None
    return None
