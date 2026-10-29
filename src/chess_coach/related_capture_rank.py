"""Rank a bounded set of legal capture examples without disclosing solutions."""

from .related_capture_features import capture_features
from .related_capture_match import candidate as score_candidate
from .related_capture_position import prompt_key


def rank(source, candidates, familiar, baseline, diagnostics=None, is_familiar=None):
    """Rank distinct unfamiliar prompts; candidates are bounded by the caller."""
    source_features = capture_features(source["prompt_fen"], source["lines"][0].split())
    if source_features is not None:
        source_features["opening"] = source.get("opening")
    if source_features is None:
        return []
    source_key = prompt_key(source["prompt_fen"])
    seen = set(familiar) | {source_key}
    diagnostics = diagnostics if diagnostics is not None else {}
    diagnostics.update(exact_source=0, familiar=0, duplicate=0)
    examples = []
    for candidate in candidates:
        item = score_candidate(candidate, source_features, set(), baseline)
        if item is None:
            continue
        reason = _excluded(item["prompt_key"], source_key, familiar, is_familiar)
        if reason:
            diagnostics[reason] += 1
        else:
            examples.append(item)
    examples.sort(key=lambda item: item["order"])
    return _diversify(examples, seen, diagnostics)


def _diversify(examples, seen, diagnostics):
    # Keep the best version of each prompt, independently of source iteration order.
    unique, games, counts = [], set(), {}
    for item in examples:
        if item["prompt_key"] in seen or (item["game"] and item["game"] in games):
            diagnostics["duplicate"] += 1
            continue
        seen.add(item["prompt_key"])
        if item["game"]:
            games.add(item["game"])
        group = item["diversity"]
        item["round"] = counts.get(group, 0)
        counts[group] = item["round"] + 1
        unique.append(item)
    return sorted(unique, key=lambda item: (item["round"], item["order"]))


def _excluded(key, source_key, familiar, is_familiar):
    if key == source_key:
        return "exact_source"
    if key in familiar or (is_familiar and is_familiar(key)):
        familiar.add(key)
        return "familiar"
    return None
