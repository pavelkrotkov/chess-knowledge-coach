"""Plan a small, deterministic session without changing evidence or schedules."""

from datetime import datetime

from .curriculum_cursor import new_state, resume_state
from .curriculum_cursor_codec import decode_cursor
from .curriculum_page import build_page
from .curriculum_request import validate_plan_request
from .curriculum_snapshot import plan_snapshot
from .db import Database
from .mastery_time import parse_utc


def daily_plan(
    db: Database,
    *,
    subject: str,
    corpus_version: str,
    limit: int = 10,
    scan_limit: int = 200,
    as_of: datetime | None = None,
    cursor: str | None = None,
) -> dict:
    with plan_snapshot(db):
        prior = decode_cursor(db, cursor) if cursor is not None else None
        requested_time = (
            as_of if as_of is not None else (parse_utc(prior["as_of"]) if prior else None)
        )
        learner, now = validate_plan_request(
            subject, corpus_version, limit, scan_limit, requested_time
        )
        if prior is None:
            state = new_state(db, learner, corpus_version, limit, scan_limit, now)
        else:
            state, now = resume_state(db, prior, learner, corpus_version, limit, scan_limit, now)
        return build_page(db, state, learner, now)
