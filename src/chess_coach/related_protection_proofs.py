"""Bound expensive protection proofs after role screening."""

from .related_capture_match import _scored
from .related_protection_features import protection_features, same_mechanism
from .related_protection_screen import plausible


def matches(item, source, baseline, budget, prompt, key, lines, *, accept=None):
    found = []
    for index, line in enumerate(lines):
        if not plausible(prompt, line.split(), source):
            continue
        if accept is not None and not accept(key):
            break
        if budget["checked"] >= budget["limit"]:
            budget["truncated"] = True
            break
        budget["checked"] += 1
        features = protection_features(prompt, line.split())
        if same_mechanism(source, features):
            match = _scored(item, source, features, prompt, key, baseline)
            match["objective_target"] = features["target_square"]
            match["protection_mechanism"] = features["mechanism"]
            found.append((match, index))
    return found
