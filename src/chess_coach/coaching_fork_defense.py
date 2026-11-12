"""Recheck optional origin-specific actions for displayed fork lessons."""

import sqlite3
import time

from .coaching_fork_defense_select import examples
from .fork_defense_contract import MAPPER
from .opening_queue_budget import BrowserBudget
from .tactical_course_budget import PreviewUnavailable

SECONDS = 3


def _lesson(lesson):
    return (lesson["family"], lesson["skill"], lesson["operation"]) == (MAPPER, "fork", "prevent")


def actions(db, subject, preview):
    groups = preview["groups"]
    empty = [{} for _ in groups]
    if not any(_lesson(group["lesson"]) for group in groups):
        return empty
    try:
        budget = BrowserBudget(db)
        budget.expires = min(budget.expires, time.monotonic() + SECONDS)
        result = [
            examples(db, subject, group["lesson"], budget) if _lesson(group["lesson"]) else {}
            for group in groups
        ]
        budget.check()
        return result
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        return empty
