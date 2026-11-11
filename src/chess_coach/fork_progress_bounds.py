"""Withhold directions when unknown attempts can reverse the sample ordering."""

from .mate_assessment_compare import SAMPLE


def _complete(sample):
    completed = ("correct", "incorrect", "unresolved")
    return sum(sample["counts"].get(key, 0) for key in completed) == SAMPLE


def direction(earlier, recent):
    samples = (earlier, recent)
    if any(s["size"] != SAMPLE or s["total"] < 5 for s in samples):
        return None
    if not all(_complete(s) for s in samples):
        return None
    if recent["low"] * earlier["total"] > earlier["high"] * recent["total"]:
        return "higher"
    if earlier["low"] * recent["total"] > recent["high"] * earlier["total"]:
        return "lower"
    return None
