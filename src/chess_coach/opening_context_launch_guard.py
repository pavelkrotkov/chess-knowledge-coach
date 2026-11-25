"""Recheck one preflight at the existing launch observation boundary."""

import sqlite3
import time

from .opening_study_source import fingerprint
from .opening_unfamiliar_guard import check
from .tactical_course_budget import SLICE_SECONDS, PreviewUnavailable
from .tactical_course_deadline import PreviewDeadline
from .tactical_exposure_practice import check as exposure


def begin(context):
    budget = context["budget"]
    budget.expires = min(budget.expires, time.monotonic() + SLICE_SECONDS)


def validate(context, db, root, subject):
    budget = context["budget"]
    try:
        with budget.scope(snapshot=False):
            check(db, root, subject, context["guard"], budget)
            task = context.get("task")
            if task and exposure(db, subject, task["prompt"]) != task["exposure"]:
                raise ValueError("opening practice exposure changed")
            if fingerprint(context["paths"]) != context["fingerprint"]:
                raise ValueError("opening context changed")
            budget.check()
    except (PreviewUnavailable, PreviewDeadline, OSError, sqlite3.Error):
        raise ValueError("opening context check unavailable") from None
