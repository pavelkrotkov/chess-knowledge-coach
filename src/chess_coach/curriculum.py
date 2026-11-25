"""Plan a small, deterministic session without changing evidence or schedules."""

from datetime import datetime

from .curriculum_cursor import new_state, resume_state
from .curriculum_cursor_codec import decode_cursor
from .curriculum_page import build_page
from .curriculum_request import validate_plan_request
from .curriculum_snapshot import plan_snapshot
from .db import Database
from .mastery_time import parse_utc
from .opening_queue_budget import BrowserBudget


def daily_plan(
    db: Database,
    *,
    subject: str,
    corpus_version: str,
    limit: int = 10,
    scan_limit: int = 200,
    as_of: datetime | None = None,
    cursor: str | None = None,
    goal: str | None = None,
    duration_minutes: int | None = None,
    renew: bool = False,
) -> dict:
    budget = None
    if not db.compat32 and not db.connection.in_transaction:
        budget = BrowserBudget(db)
    with plan_snapshot(db):
        from .curriculum_window_plan import build as build_window
        from .curriculum_window_request import requested

        window = requested(db, cursor, goal, duration_minutes, renew)
        prior = _prior(db, cursor, window)
        requested_time = (
            as_of
            if as_of is not None
            else (parse_utc(prior["as_of"]) if prior and not renew else None)
        )
        learner, now = validate_plan_request(
            subject, corpus_version, limit, scan_limit, requested_time
        )
        if window is not None:
            return build_window(
                db,
                window,
                learner,
                corpus_version,
                limit,
                scan_limit,
                now,
                budget,
                goal,
                duration_minutes,
                renew,
            )
        if prior is None:
            state = new_state(db, learner, corpus_version, limit, scan_limit, now)
        else:
            state, now = resume_state(db, prior, learner, corpus_version, limit, scan_limit, now)
        return build_page(db, state, learner, now, budget)


def _prior(db, cursor, window):
    if window:
        return window["state"]
    return decode_cursor(db, cursor) if cursor is not None else None
