"""Safely render a quick coaching scope when optional checks cannot finish."""

import sqlite3

from .coaching_quick import report
from .coaching_quick_pair import ROW_LIMIT
from .coaching_quick_scope import label
from .coaching_report import VERSION
from .recurrence_skills import PAIRS
from .tactical_course_budget import PreviewUnavailable


def preview(db, subject, pairs):
    try:
        return report(db, subject, pairs)
    except (sqlite3.Error, ValueError, TypeError, KeyError, IndexError, PreviewUnavailable):
        return {
            "kind": VERSION,
            "groups": [],
            "eligible_groups": 0,
            "failure_limits": [],
            "excluded": {},
            "coverage": {},
            "quick": {
                "patterns": [label(pair) for pair in pairs],
                "omitted": len(PAIRS) - len(pairs),
                "deferred": [label(pair) for pair in pairs],
                "scanned": 0,
                "row_limit": ROW_LIMIT,
                "changed": True,
                "practice_limited": True,
            },
        }, []
