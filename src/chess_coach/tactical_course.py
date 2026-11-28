"""Build a separate bounded, provisional local tactical-course preview."""

from .course_preview import preview_hash
from .learner_identity import normalize_identity
from .tactical_course_budget import (
    SLICE_SECONDS,
    TOTAL_SECONDS,
    Budget,
    NoPatterns,
    PreviewUnavailable,
)
from .tactical_course_choice import SLICE_SECONDS as SELECTED_SECONDS
from .tactical_course_choice import WORK_POLICY, check_budget, pairs
from .tactical_course_contract import (
    CONTRACTS,
    DEFAULT_FORK_POLICY,
    DEFAULT_FORK_VERSION,
    DEFAULT_PROTECTION_ROLES_POLICY,
    DEFAULT_PROTECTION_ROLES_VERSION,
    DEFAULT_ROLES_POLICY,
    DEFAULT_ROLES_VERSION,
    FORK_PAIR,
    FORK_VERSIONS,
    LEGACY_POLICY,
    LEGACY_VERSION,
    NAMED_POLICY,
    NAMED_VERSION,
    POLICY,
    PREVIOUS_POLICY,
    PREVIOUS_VERSION,
    PROTECTION_POLICY,
    PROTECTION_VERSION,
    QUALIFIED_FORK_VERSIONS,
    ROLE_COURSE_VERSIONS,
    SELECTED_FORK_POLICY,
    SELECTED_FORK_ROLES_POLICY,
    SELECTED_FORK_ROLES_VERSION,
    SELECTED_FORK_VERSION,
    SELECTED_POLICY,
    SELECTED_PROTECTION_ROLES_POLICY,
    SELECTED_PROTECTION_ROLES_VERSION,
    SELECTED_ROLES_POLICY,
    SELECTED_ROLES_VERSION,
    SELECTED_VERSION,
    THEMATIC_POLICY,
    THEMATIC_SELECTED_POLICY,
    THEMATIC_SELECTED_VERSION,
    THEMATIC_VERSION,
    VERSION,
)
from .tactical_course_patterns import MAX_PATTERNS, assemble
from .tactical_course_protection import PER_BAND
from .tactical_course_readiness import selection as readiness_selection
from .tactical_course_selection import CURRENT_PAIRS as CURRENT_PAIRS
from .tactical_course_selection import PAIRS as PAIRS
from .tactical_course_selection import PER_PAIR, candidates

__all__ = [
    "CONTRACTS",
    "CURRENT_PAIRS",
    "DEFAULT_FORK_POLICY",
    "DEFAULT_FORK_VERSION",
    "DEFAULT_PROTECTION_ROLES_POLICY",
    "DEFAULT_PROTECTION_ROLES_VERSION",
    "DEFAULT_ROLES_POLICY",
    "DEFAULT_ROLES_VERSION",
    "FORK_PAIR",
    "FORK_VERSIONS",
    "LEGACY_POLICY",
    "LEGACY_VERSION",
    "MAX_PATTERNS",
    "NAMED_POLICY",
    "NAMED_VERSION",
    "PAIRS",
    "PER_BAND",
    "PER_PAIR",
    "POLICY",
    "PREVIOUS_POLICY",
    "PREVIOUS_VERSION",
    "PROTECTION_POLICY",
    "PROTECTION_VERSION",
    "QUALIFIED_FORK_VERSIONS",
    "ROLE_COURSE_VERSIONS",
    "SELECTED_FORK_POLICY",
    "SELECTED_FORK_ROLES_POLICY",
    "SELECTED_FORK_ROLES_VERSION",
    "SELECTED_FORK_VERSION",
    "SELECTED_POLICY",
    "SELECTED_PROTECTION_ROLES_POLICY",
    "SELECTED_PROTECTION_ROLES_VERSION",
    "SELECTED_ROLES_POLICY",
    "SELECTED_ROLES_VERSION",
    "SELECTED_SECONDS",
    "SELECTED_VERSION",
    "SLICE_SECONDS",
    "THEMATIC_POLICY",
    "THEMATIC_SELECTED_POLICY",
    "THEMATIC_SELECTED_VERSION",
    "THEMATIC_VERSION",
    "TOTAL_SECONDS",
    "VERSION",
    "WORK_POLICY",
    "Budget",
    "NoPatterns",
    "PreviewUnavailable",
    "assemble",
    "build",
    "candidates",
    "check_budget",
    "normalize_identity",
    "pairs",
    "preview_hash",
    "readiness_selection",
]


def _policy(selected):
    if selected is None:
        version = DEFAULT_PROTECTION_ROLES_VERSION
        return version, *CONTRACTS[version], None
    chosen = pairs(selected)
    versions = {
        (("hanging_piece", "execute"),): SELECTED_ROLES_VERSION,
        (FORK_PAIR,): SELECTED_FORK_ROLES_VERSION,
        (("hanging_piece", "prevent"),): SELECTED_PROTECTION_ROLES_VERSION,
    }
    version = versions.get(tuple(chosen), THEMATIC_SELECTED_VERSION)
    return version, CONTRACTS[version][0], chosen, SELECTED_SECONDS


def build(db, subject, corpus, *, budget=None, selected=None):
    subject = normalize_identity(subject)
    if not subject or not isinstance(corpus, str) or not corpus:
        raise PreviewUnavailable("preview subject or corpus unavailable")
    # Selected work binds its own budget.
    version, policy, chosen, slice_seconds = _policy(selected)
    budget = budget or Budget(db, slice_seconds=slice_seconds)
    check_budget(selected is not None, budget)
    groups, coverage = candidates(db, subject, budget, pairs=chosen)
    patterns, chapters, unavailable, omitted = assemble(
        db,
        subject,
        corpus,
        groups,
        budget,
        allow_empty=True,
        thematic=True,
        named=version
        in {
            NAMED_VERSION,
            DEFAULT_ROLES_VERSION,
            SELECTED_ROLES_VERSION,
            DEFAULT_FORK_VERSION,
            DEFAULT_PROTECTION_ROLES_VERSION,
        },
        roles=version in ROLE_COURSE_VERSIONS,
        fork=version in QUALIFIED_FORK_VERSIONS,
        protection=version in {SELECTED_PROTECTION_ROLES_VERSION, DEFAULT_PROTECTION_ROLES_VERSION},
    )
    budget.check()
    _check_empty(patterns, selected, coverage, unavailable, chosen)
    body = {
        "kind": version,
        "policy": policy,
        "selection": {
            "pairs": [list(pair) for pair in chosen],
            "corpus_version": corpus,
            "per_pair_limit": PER_PAIR,
            "pattern_limit": MAX_PATTERNS,
            "related_match_seconds": slice_seconds or SLICE_SECONDS,
            "protection_per_band": PER_BAND,
            "ranking": "completed pairs by inspected independent failure games, then skill and operation",
            "scope": "Only completed supported pairs are ranked; this is not a global weakness ranking.",
            "coverage": coverage,
            "unavailable": unavailable,
            "unexamined_ranked_groups": omitted,
        },
        "patterns": patterns,
        "chapters": chapters,
    }
    # These bounds are part of the hashed preview and later export identity.
    if selected is not None:
        body["selection"]["work_policy"] = WORK_POLICY
        body["selection"]["total_seconds"] = TOTAL_SECONDS
    return {"kind": version, "preview": body, "preview_sha256": preview_hash(body)}


def _check_empty(patterns, selected, coverage, unavailable, chosen):
    if not patterns and selected is None:
        raise NoPatterns(readiness_selection(coverage, unavailable, chosen))
