"""Prepare one requested private course without contacting a provider."""

import os
from pathlib import Path

from .opening_queue_location import location
from .tactical_course import build as build_preview
from .tactical_course_budget import Budget
from .tactical_course_capacity import output
from .tactical_course_deadline import PreviewDeadline
from .tactical_course_publish import publish
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
        budget = Budget(db)
        candidate = build_preview(db, learner, corpus, budget=budget)
        result = build_export(db, learner, corpus, candidate, budget)
        if not result["export"]["chapters"]:
            raise ValueError("no supported chapters")
        path, needed = output(root, directory, result, budget)
        if needed:
            publish(path, result, budget, readonly=True)
        finish(directory, database, learner, corpus, requested, old_offer, result, path, budget)
    except (Exception, PreviewDeadline):
        failed(directory, database, learner, corpus, requested)
