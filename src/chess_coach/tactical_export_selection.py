"""Validate saved preview selection and coverage policy."""

from .tactical_course_budget import SLICE_SECONDS, TOTAL_SECONDS
from .tactical_course_choice import SLICE_SECONDS as SELECTED_SECONDS
from .tactical_course_choice import WORK_POLICY, check_budget
from .tactical_course_contract import (
    CONTRACTS,
    PROTECTION_VERSION,
    pairs_for,
)
from .tactical_course_contract import (
    MODERN as MODERN,
)
from .tactical_course_contract import (
    NAMED as NAMED,
)
from .tactical_course_contract import (
    SELECTED as SELECTED,
)
from .tactical_course_contract import (
    THEMATIC as THEMATIC,
)
from .tactical_course_patterns import MAX_PATTERNS
from .tactical_course_protection import PER_BAND
from .tactical_course_selection import PER_PAIR
from .tactical_export_coverage import coverage
from .tactical_export_gaps import omissions


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


def selection(body, corpus):
    selection = body["selection"]
    contract = CONTRACTS.get(body.get("kind"))
    if contract is None or body.get("policy") != contract[0]:
        raise ValueError("unsupported preview policy")
    # A selected preview must bind its canonical pairs and exact work policy.
    selected = body["kind"] in SELECTED
    pairs = pairs_for(body["kind"], selection["pairs"])
    expected = {
        "corpus_version": corpus,
        "pairs": [list(pair) for pair in pairs],
        "per_pair_limit": PER_PAIR,
        "pattern_limit": MAX_PATTERNS,
        "related_match_seconds": SELECTED_SECONDS if selected else SLICE_SECONDS,
        "ranking": "completed pairs by inspected independent failure games, then skill and operation",
        "scope": "Only completed supported pairs are ranked; this is not a global weakness ranking.",
    }
    if selected:
        expected.update(work_policy=WORK_POLICY, total_seconds=TOTAL_SECONDS)
    if {key: selection[key] for key in expected} != expected:
        raise ValueError("preview selection or bounds changed")
    # A deferred pair cannot supply a pattern; omissions must match coverage.
    coverage(selection["coverage"], pairs)
    _omissions(selection, pairs, body["kind"] in MODERN)
    return pairs


def context(body, corpus, budget):
    pairs = selection(body, corpus)
    kind = body["kind"]
    check_budget(kind in SELECTED, budget)
    modern = kind in MODERN
    gaps = omissions(
        body["selection"],
        pairs=pairs,
        modern=modern,
        owned_deadline=kind in MODERN - {PROTECTION_VERSION},
    )
    return pairs, modern, gaps, kind in THEMATIC, kind
