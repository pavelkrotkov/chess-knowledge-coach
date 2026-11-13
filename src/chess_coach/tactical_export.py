"""Validate a selected tactical preview into a separate local candidate."""

from .course_preview import preview_hash
from .learner_identity import normalize_identity
from .tactical_course import LEGACY_VERSION as LEGACY_PREVIEW_VERSION
from .tactical_export_chapters import verify
from .tactical_export_contract import validate
from .tactical_export_coverage import selected as covered
from .tactical_export_gaps import OWN, omissions, selected
from .tactical_export_selection import selection
from .tactical_export_sources import lesson

LEGACY_VERSION = "local-tactical-course-export-v1"
LEGACY_POLICY = "tactical-export-verification-v1"
VERSION = "local-tactical-course-export-v2"
POLICY = "tactical-export-verification-v2"


def _chapters(chapters, index):
    if index >= len(chapters) or chapters[index]["source"]["type"] != "own-game":
        raise ValueError("owned chapter order differs")
    end = index + 1
    if end < len(chapters) and chapters[end]["source"]["type"] in {"public", "corpus"}:
        end += 1
    return chapters[index:end], end


def _contract(body):
    if body["kind"] == LEGACY_PREVIEW_VERSION:
        return LEGACY_VERSION, LEGACY_POLICY
    return VERSION, POLICY


def build(db, subject, corpus, envelope, budget):
    subject = normalize_identity(subject)
    if not subject:
        raise ValueError("learner identity unavailable")
    with budget.scope(snapshot=False):
        body = validate(envelope, corpus)
    pairs = selection(body, corpus)
    index, seen = 0, set()
    gaps = omissions(body["selection"], pairs=pairs)
    for pattern in body["patterns"]:
        pair = (pattern["skill"], pattern["operation"])
        if pair in seen:
            raise ValueError("duplicate tactical pattern")
        seen.add(pair)
        group, index = _chapters(body["chapters"], index)
        covered(pattern, body["selection"]["coverage"])
        selected(pattern, group, gaps)
        current = lesson(db, subject, pattern, budget, pairs=pairs)
        verify(db, subject, corpus, pattern, current, group, budget)
    if any(reason != OWN and pair not in seen for pair, reason in gaps.items()):
        raise ValueError("related omission has no selected pattern")
    if index != len(body["chapters"]):
        raise ValueError("unexpected chapter order")
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
