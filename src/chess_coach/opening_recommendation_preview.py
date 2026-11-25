"""Build a chosen, current recommendation from the existing revision course."""

import time

from .fact_fingerprint import canonical, digest
from .opening_decision import inspect
from .opening_explore_view import report as explore
from .opening_queue_budget import BrowserBudget
from .opening_recommendation_paths import inputs
from .opening_recommendation_selection import rationale_snapshot, selection
from .opening_recommendation_text import annotate, note
from .opening_revision_course import preview as course_preview
from .opening_study_source import fingerprint
from .style_schedule_budget import history_budget

SCHEMA = "opening-revision-course-v2"
SECONDS = 25


def preview(db, root, learner, game_id, position_id, move, *, deadline=None, with_identity=False):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    if deadline is not None:
        budget.expires = min(budget.expires, deadline)
    with budget.scope(snapshot=False):
        decision = inspect(db, game_id, position_id, learner)
    with history_budget(deadline=budget.expires):
        paths = inputs(db, root, learner, decision, budget)
    before = fingerprint(paths)
    report = explore(db, root, learner, revision=True, deadline=budget.expires)
    selected = selection(report, game_id, position_id, move)
    original = course_preview(
        db, root, learner, game_id, position_id, move, deadline=budget.expires, with_identity=True
    )
    identity = original.pop("_identity")
    chapters = list(original["chapters"])
    chapters[0] = annotate(
        chapters[0], note(original["choice"], selected, report["revision_judgments"])
    )
    rationale = rationale_snapshot(report, move, digest(canonical(before)))
    with history_budget(deadline=budget.expires):
        current_paths = inputs(db, root, learner, decision, budget)
    budget.check()
    if current_paths != paths or fingerprint(paths) != before:
        raise ValueError("opening recommendation source changed")
    payload = {
        "schema": SCHEMA,
        "course": original["version"],
        "chapters": chapters,
        "rationale": rationale,
    }
    return {
        **original,
        "version": digest(canonical(payload)),
        "schema": SCHEMA,
        "chapters": chapters,
        "rationale": rationale,
        **({"_paths": paths, "_identity": identity} if with_identity else {}),
    }
