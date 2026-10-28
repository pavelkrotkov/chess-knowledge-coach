"""Plan a small, deterministic session without changing evidence or schedules."""

from datetime import datetime

from .curriculum_due import due_candidates
from .curriculum_evidence import evidence_summary
from .curriculum_query import new_items
from .curriculum_request import validate_plan_request
from .curriculum_selection import select
from .curriculum_snapshot import plan_snapshot
from .db import Database


def daily_plan(
    db: Database,
    *,
    subject: str,
    corpus_version: str,
    limit: int = 10,
    scan_limit: int = 200,
    as_of: datetime | None = None,
) -> dict:
    learner, now = validate_plan_request(subject, corpus_version, limit, scan_limit, as_of)
    with plan_snapshot(db):
        return _plan(db, learner, corpus_version, limit, scan_limit, now)


def _plan(
    db: Database, learner: str, corpus_version: str, limit: int, scan_limit: int, now: datetime
) -> dict:
    summary = evidence_summary(db, learner, now)
    due, due_more, due_scanned = due_candidates(db, now, scan_limit)
    items, seen = select(due, limit, summary, set())
    corpus, more, scanned, corpus_state = new_items(
        db, corpus_version, scan_limit, due_more, len(items), limit
    )
    selected, _ = select(corpus, limit - len(items), summary, seen)
    return {
        "as_of": now.isoformat(),
        "evidence": summary,
        "corpus_status": corpus_state,
        "scan": {
            "due_examined": due_scanned,
            "due_incomplete": due_more,
            "corpus_examined": scanned,
            "corpus_incomplete": more,
        },
        "items": items + selected,
    }
