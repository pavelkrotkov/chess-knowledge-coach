"""Validate a selected tactical preview into a separate local candidate."""

from .course_preview import preview_hash
from .learner_identity import normalize_identity
from .tactical_export_chapters import verify
from .tactical_export_contract import contract as _contract
from .tactical_export_contract import validate
from .tactical_export_groups import groups
from .tactical_export_selection import context
from .tactical_export_sources import lesson

LEGACY_VERSION = "local-tactical-course-export-v1"
LEGACY_POLICY = "tactical-export-verification-v1"
PREVIOUS_VERSION = "local-tactical-course-export-v2"
PREVIOUS_POLICY = "tactical-export-verification-v2"
PROTECTION_VERSION = "local-tactical-course-export-v3"
PROTECTION_POLICY = "tactical-export-verification-v3"
VERSION = "local-tactical-course-export-v4"
POLICY = "tactical-export-verification-v4"
SELECTED_VERSION = "local-tactical-course-export-v5"
SELECTED_POLICY = "tactical-export-verification-v5"
THEMATIC_EXPORT_VERSION = "local-tactical-course-export-v6"
THEMATIC_SELECTED_EXPORT_VERSION = "local-tactical-course-export-v7"


def build(db, subject, corpus, envelope, budget, *, artifact=None):
    subject = normalize_identity(subject)
    if not subject:
        raise ValueError("learner identity unavailable")
    with budget.scope(snapshot=False):
        body = validate(envelope, corpus)
    pairs, modern, gaps, thematic, _ = context(body, corpus, budget)
    for pattern, group, roles, named in groups(body, gaps, modern=modern):
        current = lesson(db, subject, pattern, budget, pairs=pairs)
        verify(
            db,
            subject,
            corpus,
            pattern,
            current,
            group,
            budget,
            modern=modern,
            thematic=thematic,
            named=named,
            roles=roles,
            artifact=artifact,
        )
    # A commit after the final source check invalidates the entire candidate.
    budget.check()
    version, policy = _contract(body)
    result = {
        "kind": version,
        "policy": policy,
        "preview_sha256": envelope["preview_sha256"],
        "ranking_qualification": "Preview ranking and coverage are retained as recorded, not freshly reranked; supporting sources and included chapters were revalidated.",
        "selection": body["selection"],
        "patterns": body["patterns"],
        "chapters": body["chapters"],
    }
    with budget.scope(snapshot=False):
        return {"kind": version, "export": result, "export_sha256": preview_hash(result)}
