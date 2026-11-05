"""Validate a selected tactical preview into a separate local candidate."""

from .course_preview import preview_hash
from .learner_identity import normalize_identity
from .tactical_export_chapters import verify
from .tactical_export_contract import validate
from .tactical_export_sources import lesson

VERSION = "local-tactical-course-export-v1"
POLICY = "tactical-export-verification-v1"


def _chapters(chapters, index):
    if index >= len(chapters) or chapters[index]["source"]["type"] != "own-game":
        raise ValueError("owned chapter order differs")
    end = index + 1
    if end < len(chapters) and chapters[end]["source"]["type"] in {"public", "corpus"}:
        end += 1
    return chapters[index:end], end


def build(db, subject, corpus, envelope, budget):
    subject = normalize_identity(subject)
    if not subject:
        raise ValueError("learner identity unavailable")
    with budget.scope(snapshot=False):
        body = validate(envelope, corpus)
    index, seen = 0, set()
    for pattern in body["patterns"]:
        pair = (pattern["skill"], pattern["operation"])
        if pair in seen:
            raise ValueError("duplicate tactical pattern")
        seen.add(pair)
        group, index = _chapters(body["chapters"], index)
        current = lesson(db, subject, pattern, budget)
        verify(db, subject, corpus, pattern, current, group, budget)
    if index != len(body["chapters"]):
        raise ValueError("unexpected chapter order")
    # A commit after the final source check invalidates the entire candidate.
    budget.check()
    result = {
        "kind": VERSION,
        "policy": POLICY,
        "preview_sha256": envelope["preview_sha256"],
        "ranking_qualification": "Preview ranking and coverage are retained as recorded, not freshly reranked; supporting sources and included chapters were revalidated.",
        "selection": body["selection"],
        "patterns": body["patterns"],
        "chapters": body["chapters"],
    }
    with budget.scope(snapshot=False):
        return {"kind": VERSION, "export": result, "export_sha256": preview_hash(result)}
