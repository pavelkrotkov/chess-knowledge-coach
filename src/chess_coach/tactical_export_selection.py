"""Validate saved preview selection and coverage policy."""

from .tactical_course_budget import SLICE_SECONDS
from .tactical_course_patterns import MAX_PATTERNS
from .tactical_course_selection import PAIRS, PER_PAIR
from .tactical_export_coverage import coverage


def _omissions(selection):
    omitted = selection["unexamined_ranked_groups"]
    if type(omitted) is not int or not 0 <= omitted <= len(PAIRS):
        raise ValueError("invalid preview ranking coverage")
    if not isinstance(selection["unavailable"], list) or len(selection["unavailable"]) > 8:
        raise ValueError("invalid preview omissions")


def selection(body, corpus):
    selection = body["selection"]
    if body.get("policy") != "provisional-recurring-tactics-v1":
        raise ValueError("unsupported preview policy")
    expected = [
        corpus,
        [list(pair) for pair in PAIRS],
        PER_PAIR,
        MAX_PATTERNS,
        SLICE_SECONDS,
        "completed pairs by inspected independent failure games, then skill and operation",
        "Only completed supported pairs are ranked; this is not a global weakness ranking.",
    ]
    actual = [
        selection[key]
        for key in (
            "corpus_version",
            "pairs",
            "per_pair_limit",
            "pattern_limit",
            "related_match_seconds",
            "ranking",
            "scope",
        )
    ]
    if actual != expected:
        raise ValueError("preview selection or bounds changed")
    coverage(selection["coverage"])
    _omissions(selection)
