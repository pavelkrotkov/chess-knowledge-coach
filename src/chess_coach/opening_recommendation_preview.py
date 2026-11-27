"""Build a chosen, current recommendation from the existing revision course."""

import time

from .fact_fingerprint import canonical, digest
from .opening_decision import inspect
from .opening_explore_view import report as explore
from .opening_queue_budget import BrowserBudget
from .opening_recommendation_paths import inputs
from .opening_recommendation_roles import LEGACY_SCHEMA as SCHEMA
from .opening_recommendation_roles import three_roles
from .opening_recommendation_selection import selection
from .opening_recommendation_snapshot import rationale_snapshot
from .opening_recommendation_text import annotate, note
from .opening_revision_course import preview as course_preview
from .opening_study_source import fingerprint

SECONDS = 25


def legacy(db, root, learner, game_id, position_id, move, *, deadline=None, with_identity=False):
    budget = BrowserBudget(db)
    budget.expires = min(budget.expires, time.monotonic() + SECONDS)
    if deadline is not None:
        budget.expires = min(budget.expires, deadline)
    with budget.scope(snapshot=False):
        decision = inspect(db, game_id, position_id, learner)
    paths = inputs(db, root, learner, decision, budget)
    before = fingerprint(paths)
    report = explore(db, root, learner, revision=True, deadline=budget.expires)
    selected = selection(report, game_id, position_id, move)
    original = course_preview(
        db, root, learner, game_id, position_id, move, deadline=budget.expires, with_identity=True
    )
    identity = original.pop("_identity")
    chapters = list(original["chapters"])
    chapters[0] = annotate(chapters[0], note(original["choice"], selected, report))
    rationale = rationale_snapshot(report, move, digest(canonical(before)))
    current_paths = inputs(db, root, learner, decision, budget)
    budget.check()
    if current_paths != paths or fingerprint(paths) != before:
        raise ValueError("opening recommendation source changed")
    budget.check()
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
        **(
            {"_paths": paths, "_identity": identity, "_deadline": budget.expires}
            if with_identity
            else {}
        ),
    }


def preview(db, root, learner, game_id, position_id, move, *, deadline=None, with_identity=False):
    return three_roles(
        legacy(
            db,
            root,
            learner,
            game_id,
            position_id,
            move,
            deadline=deadline,
            with_identity=with_identity,
        )
    )
