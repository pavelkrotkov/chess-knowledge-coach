"""Emit only fixed, non-identifying renewal refusal diagnostics."""

import logging
import sqlite3

from .tactical_course_budget import PreviewUnavailable
from .tactical_course_deadline import PreviewDeadline

_PHASES = {"request": "renewal_request", "reoffer": "renewal_reoffer"}
_VALUES = {
    "scheduled prompt unavailable": "source_unavailable",
    "scheduled scan incomplete": "scan_incomplete",
    "previous offers could not be rechecked": "recheck_unavailable",
    "practice window scope changed": "selection_or_scope",
    "practice window limit changed": "selection_or_scope",
    "a practice window is required for renewal": "selection_or_scope",
}


def refusal(phase, error):
    if isinstance(error, PreviewDeadline):
        category = "deadline"
    elif isinstance(error, PreviewUnavailable):
        category = "budget_or_source_change"
    elif isinstance(error, sqlite3.Error):
        category = "database"
    elif isinstance(error, OSError):
        category = "source_io"
    elif isinstance(error, ValueError):
        category = _VALUES.get(str(error), "refused")
    else:
        category = "refused"
    logging.getLogger(__name__).warning(
        "renewal_refusal phase=%s category=%s", _PHASES[phase], category
    )
