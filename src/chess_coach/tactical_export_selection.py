"""Validate saved preview selection and coverage policy."""

from .tactical_course import LEGACY_POLICY, LEGACY_VERSION, POLICY, VERSION
from .tactical_course_budget import SLICE_SECONDS
from .tactical_course_patterns import MAX_PATTERNS
from .tactical_course_selection import CURRENT_PAIRS, PAIRS, PER_PAIR
from .tactical_export_coverage import coverage


def _omissions(selection, pairs):
    omitted = selection["unexamined_ranked_groups"]
    if type(omitted) is not int or not 0 <= omitted <= len(pairs):
        raise ValueError("invalid preview ranking coverage")
    if not isinstance(selection["unavailable"], list) or len(selection["unavailable"]) > 2 * len(
        pairs
    ):
        raise ValueError("invalid preview omissions")


def selection(body, corpus):
    selection = body["selection"]
    contracts = {LEGACY_VERSION: (LEGACY_POLICY, PAIRS), VERSION: (POLICY, CURRENT_PAIRS)}
    contract = contracts.get(body.get("kind"))
    if contract is None or body.get("policy") != contract[0]:
        raise ValueError("unsupported preview policy")
    pairs = contract[1]
    expected = [
        corpus,
        [list(pair) for pair in pairs],
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
    coverage(selection["coverage"], pairs)
    _omissions(selection, pairs)
    return pairs
