"""Select only external lines that actually match a certified pin branch."""

from .related_capture_match import _scored
from .related_capture_position import prompt_key
from .related_fork_lines import bind_lines
from .related_pin_candidates import matches
from .related_pin_candidates import prompt as candidate_prompt


def scorer(budget):
    def score(item, source, seen, baseline):
        if budget["truncated"]:
            return None
        return _candidate(item, source, seen, baseline, budget)

    return score


def _candidate(item, source, seen, baseline, budget):
    try:
        board, lines = candidate_prompt(item)
    except (ValueError, TypeError, KeyError):
        budget["unknown"] += 1
        return None
    prompt = board.fen()
    if prompt_key(prompt) in seen:
        return None
    selected = matches(board, lines, source, budget)
    if not selected:
        return None
    shape, _, _ = selected[0][1]
    result = _scored(item, source, shape, prompt, prompt_key(prompt), baseline)
    bind_lines(result, lines, [index for index, _ in selected])
    result["candidate_certificates"] = [
        {"line_index": index, "proof": found[1], "branch": found[2]} for index, found in selected
    ]
    return result
