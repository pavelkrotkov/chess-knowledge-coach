"""Replay both source-bound harder lineages under one caller deadline."""

from .capture_common_control import compatible
from .capture_context_comparison import _profile as selected_capture_profile
from .capture_context_comparison import profile as capture_profile
from .capture_harder_lineage import verify as verify_capture
from .fork_common_profile import profile as fork_profile
from .fork_harder_lineage import verify as verify_fork


def verify(db, subject, corpus, capture, fork, as_of, check):
    if fork["controls"]["admission"] == "harder":
        verify_capture(db, subject, corpus, capture["source"], check)
        verify_fork(db, subject, corpus, fork, as_of, check)


def profiles(db, subject, corpus, as_of, capture, fork, check, option, admitted):
    try:
        left = _capture(db, subject, corpus, as_of, capture, option, check)
        right = fork_profile(db, subject, corpus, as_of, fork, check, admitted=admitted)
        if left is None or right is None or not compatible(db, left, right, corpus):
            return None
        verify(db, subject, corpus, left, right, as_of, check)
        return left, right
    except (ValueError, TypeError, KeyError, IndexError):
        return None


def _capture(db, subject, corpus, as_of, report, option, check):
    if option is None:
        return capture_profile(db, subject, corpus, as_of, report, check)
    if not report["comparable"] or not report["boundary"] or report["historical"]:
        return None
    return selected_capture_profile(db, subject, corpus, as_of, report, option, check)
