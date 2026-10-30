"""Score matching mate structures using shared transfer ranking."""

from .related_capture_match import _scored
from .related_capture_position import prompt_key


def match(candidate, source, seen, baseline, prompt, features):
    if not prompt or not features:
        return None
    if any(source[key] != features[key] for key in ("mover", "target", "timing", "geometry")):
        return None
    key = prompt_key(prompt)
    if key in seen:
        return None
    return _scored(candidate, source, features, prompt, key, baseline)
