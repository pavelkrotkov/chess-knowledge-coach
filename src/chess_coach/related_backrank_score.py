"""Require the same witnessed back-rank mechanism before transfer ranking."""

from .related_mate_score import match as mate_match


def match(candidate, source, seen, baseline, prompt, features):
    if features is None or source.get("backrank") != features.get("backrank"):
        return None
    return mate_match(candidate, source, seen, baseline, prompt, features)
