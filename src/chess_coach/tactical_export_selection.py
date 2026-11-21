"""Validate saved preview selection and coverage policy."""

from .tactical_course import CONTRACTS, PROTECTION_VERSION, SELECTED_VERSION, VERSION
from .tactical_course_budget import SLICE_SECONDS, TOTAL_SECONDS
from .tactical_course_choice import SLICE_SECONDS as SELECTED_SECONDS
from .tactical_course_choice import WORK_POLICY, from_pairs
from .tactical_course_patterns import MAX_PATTERNS
from .tactical_course_protection import PER_BAND
from .tactical_course_selection import PER_PAIR
from .tactical_export_coverage import coverage


def _omissions(selection, pairs, modern):
    if modern and selection.get("protection_per_band") != PER_BAND:
        raise ValueError("protection scan bound changed")
    omitted = selection["unexamined_ranked_groups"]
    if type(omitted) is not int or not 0 <= omitted <= len(pairs):
        raise ValueError("invalid preview ranking coverage")
    if not isinstance(selection["unavailable"], list) or len(selection["unavailable"]) > 2 * len(
        pairs
    ):
        raise ValueError("invalid preview omissions")


def _pairs(selection, contract, selected):
    if not selected:
        return contract[1]
    if (
        selection.get("work_policy") != WORK_POLICY
        or selection.get("total_seconds") != TOTAL_SECONDS
    ):
        raise ValueError("selected work policy changed")
    return from_pairs(selection["pairs"])


def selection(body, corpus):
    selection = body["selection"]
    contract = CONTRACTS.get(body.get("kind"))
    if contract is None or body.get("policy") != contract[0]:
        raise ValueError("unsupported preview policy")
    # A selected preview must bind its canonical pairs and exact work policy.
    selected = body["kind"] == SELECTED_VERSION
    pairs = _pairs(selection, contract, selected)
    expected = [
        corpus,
        [list(pair) for pair in pairs],
        PER_PAIR,
        MAX_PATTERNS,
        SELECTED_SECONDS if selected else SLICE_SECONDS,
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
    # A deferred pair cannot supply a pattern; omissions must match coverage.
    coverage(selection["coverage"], pairs)
    _omissions(selection, pairs, body["kind"] in {PROTECTION_VERSION, VERSION, SELECTED_VERSION})
    return pairs
