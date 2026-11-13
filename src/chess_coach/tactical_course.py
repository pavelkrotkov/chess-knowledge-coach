"""Build a separate bounded, provisional local tactical-course preview."""

from .course_preview import preview_hash
from .learner_identity import normalize_identity
from .tactical_course_budget import SLICE_SECONDS, Budget, PreviewUnavailable
from .tactical_course_patterns import MAX_PATTERNS, assemble
from .tactical_course_selection import CURRENT_PAIRS, PER_PAIR, candidates

LEGACY_VERSION = "local-tactical-course-v1"
LEGACY_POLICY = "provisional-recurring-tactics-v1"
VERSION = "local-tactical-course-v2"
POLICY = "provisional-recurring-tactics-v2"


def build(db, subject, corpus, *, budget=None):
    subject = normalize_identity(subject)
    if not subject or not isinstance(corpus, str) or not corpus:
        raise PreviewUnavailable("preview subject or corpus unavailable")
    budget = budget or Budget(db)
    groups, coverage = candidates(db, subject, budget)
    patterns, chapters, unavailable, omitted = assemble(db, subject, corpus, groups, budget)
    budget.check()
    body = {
        "kind": VERSION,
        "policy": POLICY,
        "selection": {
            "pairs": [list(pair) for pair in CURRENT_PAIRS],
            "corpus_version": corpus,
            "per_pair_limit": PER_PAIR,
            "pattern_limit": MAX_PATTERNS,
            "related_match_seconds": SLICE_SECONDS,
            "ranking": "completed pairs by inspected independent failure games, then skill and operation",
            "scope": "Only completed supported pairs are ranked; this is not a global weakness ranking.",
            "coverage": coverage,
            "unavailable": unavailable,
            "unexamined_ranked_groups": omitted,
        },
        "patterns": patterns,
        "chapters": chapters,
    }
    return {"kind": VERSION, "preview": body, "preview_sha256": preview_hash(body)}
