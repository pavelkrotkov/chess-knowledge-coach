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
from .tactical_course_patterns import MAX_PATTERNS, assemble
from .tactical_course_protection import PER_BAND
from .tactical_course_readiness import selection as readiness_selection
from .tactical_course_selection import CURRENT_PAIRS, PAIRS, PER_PAIR, candidates

LEGACY_VERSION = "local-tactical-course-v1"
LEGACY_POLICY = "provisional-recurring-tactics-v1"
PREVIOUS_VERSION = "local-tactical-course-v2"
PREVIOUS_POLICY = "provisional-recurring-tactics-v2"
PROTECTION_VERSION = "local-tactical-course-v3"
PROTECTION_POLICY = "provisional-recurring-tactics-v3"
VERSION = "local-tactical-course-v4"
POLICY = "provisional-recurring-tactics-v4"
SELECTED_VERSION = "local-tactical-course-v5"
SELECTED_POLICY = "provisional-recurring-tactics-v5"
THEMATIC_VERSION = "local-tactical-course-v6"
THEMATIC_POLICY = "provisional-recurring-tactics-v6"
THEMATIC_SELECTED_VERSION = "local-tactical-course-v7"
THEMATIC_SELECTED_POLICY = "provisional-recurring-tactics-v7"
NAMED_VERSION = "local-tactical-course-v8"
NAMED_POLICY = "provisional-recurring-tactics-v8"
DEFAULT_ROLES_VERSION = "local-tactical-course-v9"
DEFAULT_ROLES_POLICY = "provisional-recurring-tactics-v9"
SELECTED_ROLES_VERSION = "local-tactical-course-v10"
SELECTED_ROLES_POLICY = "provisional-recurring-tactics-v10"
SELECTED_FORK_VERSION = "local-tactical-course-v11"
SELECTED_FORK_POLICY = "provisional-recurring-tactics-v11"
SELECTED_FORK_ROLES_VERSION = "local-tactical-course-v12"
SELECTED_FORK_ROLES_POLICY = "provisional-recurring-tactics-v12"
DEFAULT_FORK_VERSION = "local-tactical-course-v13"
DEFAULT_FORK_POLICY = "provisional-recurring-tactics-v13"
SELECTED_PROTECTION_ROLES_VERSION = "local-tactical-course-v14"
SELECTED_PROTECTION_ROLES_POLICY = "provisional-recurring-tactics-v14"
# Only selected fork versions use the eight-second slice; the default keeps two seconds.
FORK_VERSIONS = {SELECTED_FORK_VERSION, SELECTED_FORK_ROLES_VERSION}
QUALIFIED_FORK_VERSIONS = {*FORK_VERSIONS, DEFAULT_FORK_VERSION}
ROLE_COURSE_VERSIONS = {
    DEFAULT_ROLES_VERSION,
    SELECTED_ROLES_VERSION,
    SELECTED_FORK_ROLES_VERSION,
    DEFAULT_FORK_VERSION,
    SELECTED_PROTECTION_ROLES_VERSION,
}
FORK_PAIR = ("fork", "execute")
CONTRACTS = {
    LEGACY_VERSION: (LEGACY_POLICY, PAIRS),
    PREVIOUS_VERSION: (PREVIOUS_POLICY, CURRENT_PAIRS),
    PROTECTION_VERSION: (PROTECTION_POLICY, CURRENT_PAIRS),
    VERSION: (POLICY, CURRENT_PAIRS),
    SELECTED_VERSION: (SELECTED_POLICY, None),
    THEMATIC_VERSION: (THEMATIC_POLICY, CURRENT_PAIRS),
    THEMATIC_SELECTED_VERSION: (THEMATIC_SELECTED_POLICY, None),
    NAMED_VERSION: (NAMED_POLICY, None),
    DEFAULT_ROLES_VERSION: (DEFAULT_ROLES_POLICY, CURRENT_PAIRS),
    SELECTED_ROLES_VERSION: (SELECTED_ROLES_POLICY, None),
    SELECTED_FORK_VERSION: (SELECTED_FORK_POLICY, [FORK_PAIR]),
    SELECTED_FORK_ROLES_VERSION: (SELECTED_FORK_ROLES_POLICY, [FORK_PAIR]),
    DEFAULT_FORK_VERSION: (DEFAULT_FORK_POLICY, CURRENT_PAIRS),
    SELECTED_PROTECTION_ROLES_VERSION: (
        SELECTED_PROTECTION_ROLES_POLICY,
        [("hanging_piece", "prevent")],
    ),
}


def _policy(selected):
    if selected is None:
        return DEFAULT_FORK_VERSION, DEFAULT_FORK_POLICY, CURRENT_PAIRS, None
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
        in {NAMED_VERSION, DEFAULT_ROLES_VERSION, SELECTED_ROLES_VERSION, DEFAULT_FORK_VERSION},
        roles=version in ROLE_COURSE_VERSIONS,
        fork=version in QUALIFIED_FORK_VERSIONS,
        protection=version == SELECTED_PROTECTION_ROLES_VERSION,
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
