"""Prepare one requested private course without contacting a provider."""

import os
from pathlib import Path

from .opening_queue_location import location
from .tactical_course import build as build_preview
from .tactical_course_budget import Budget, NoPatterns
from .tactical_course_capacity import output
from .tactical_course_choice import SLICE_SECONDS as SELECTED_SECONDS
from .tactical_course_deadline import PreviewDeadline
from .tactical_course_publish import publish
from .tactical_course_worker_empty import record_diagnostic, record_empty, require_chapters
from .tactical_course_worker_state import claim, failed, finish
from .tactical_export import build as build_export


def run(db, learner, root):
    if not root or not os.environ.get("CHESS_CORPUS"):
        return
    root = Path(root).resolve(strict=True)
    corpus = os.environ["CHESS_CORPUS"]
    directory, database = location(db, root, learner)
    claimed = claim(directory, database, learner, corpus)
    if claimed is None:
        return
    requested, old_offer = claimed
    try:
        _prepare(db, learner, corpus, root, directory, database, requested, old_offer)
    except (Exception, PreviewDeadline):
        failed(directory, database, learner, corpus, requested)


def _prepare(db, learner, corpus, root, directory, database, requested, old_offer):
    selected = requested.get("selection")
    budget = Budget(db, slice_seconds=SELECTED_SECONDS if selected is not None else None)
    try:
        candidate = build_preview(db, learner, corpus, budget=budget, selected=selected)
    except NoPatterns as diagnostic:
        record_diagnostic(
            directory, database, learner, corpus, requested, old_offer, budget, diagnostic
        )
        return
    if not candidate["preview"]["chapters"]:
        record_empty(directory, database, learner, corpus, requested, old_offer, budget, candidate)
        return
    from .tactical_course_fork_provenance import retain

    retain(db, root, learner, candidate, budget)
    result = build_export(db, learner, corpus, candidate, budget)
    require_chapters(result)
    path, needed = output(root, directory, result, budget)
    if needed:
        publish(path, result, budget, readonly=True)
    finish(directory, database, learner, corpus, requested, old_offer, result, path, budget)
