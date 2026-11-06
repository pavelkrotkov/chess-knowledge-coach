"""Cooperatively bound one completed coaching pattern and its practice links."""

import sqlite3
import time

from .coaching_quick_pair import build
from .coaching_quick_practice import choose
from .tactical_course_budget import PreviewUnavailable

PAIR_SECONDS = 3.0


def _check(budget, until):
    def check():
        budget.check()
        if time.monotonic() >= until:
            raise PreviewUnavailable("coaching scope deadline")

    return check


def run_pair(db, learner, pair, budget):
    check = _check(budget, min(budget.expires, time.monotonic() + PAIR_SECONDS))
    lessons, truncated, scanned = build(db, learner, pair, check)
    check()
    practice = []
    practice_limited = False
    for group in lessons:
        try:
            practice.append(choose(db, learner, group, check))
        except (ValueError, TypeError, KeyError, IndexError, sqlite3.Error, PreviewUnavailable):
            practice.append(None)
            practice_limited = True
    return lessons, practice, truncated, scanned, practice_limited
