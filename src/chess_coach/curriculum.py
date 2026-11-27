"""Plan a small, deterministic session without changing evidence or schedules."""

from datetime import datetime

from .curriculum_cursor import new_state as new_state
from .curriculum_request import prior, validate_plan_request
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
    _due_recheck: bool = False,
    project_root=None,
) -> dict:
    from .capture_certificate_store import scope

    db.capture_root = scope(project_root, db.capture_root)
    budget = _budget(db, project_root)
    with plan_snapshot(db):
        from .curriculum_window_plan import build as build_window
        from .curriculum_window_request import requested

        window = requested(db, cursor, goal, duration_minutes, renew, _due_recheck)
        prior_state = prior(db, cursor, window)
        requested_time = (
            as_of
            if as_of is not None
            else (parse_utc(prior_state["as_of"]) if prior_state and not renew else None)
        )
        learner, now = validate_plan_request(
            subject, corpus_version, limit, scan_limit, requested_time
        )
        from .curriculum_capture_guard import check as check_capture
        from .curriculum_capture_guard import window as finish_window

        if not renew:
            check_capture(db, prior_state, learner, project_root, budget)
        if window is not None:
            page = build_window(
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
            return finish_window(db, page, learner, project_root, budget)
        from .curriculum_plain_plan import build as build_plain

        return build_plain(
            db,
            prior_state,
            learner,
            corpus_version,
            limit,
            scan_limit,
            now,
            budget,
            project_root,
            new_state,
        )


def _budget(db, project_root):
    if db.compat32 or db.connection.in_transaction:
        return None
    return BrowserBudget(db, project_root=project_root)
