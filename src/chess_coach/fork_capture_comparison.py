"""Compare independently qualified capture and fork first assessments."""

from .capture_common_control import compatible
from .capture_context_comparison import profile as capture_profile
from .capture_game_trend_report import report as capture_report
from .dated_game_cohort_identity import identity
from .fork_common_profile import profile as fork_profile


def compare(db, subject, corpus, root, as_of, fork, check):
    capture = capture_report(db, subject, root, check=check, as_of=as_of)
    cohort = identity(capture)
    if cohort is None or cohort != identity(fork):
        return None
    profiles = _profiles(db, subject, corpus, as_of, capture, fork, check)
    if profiles is None:
        return None
    left, right = profiles
    capture_result = left["source"]["practice"]["result"]
    fork_result = right["practice"]["result"]
    if capture_result == fork_result:
        return None
    return {"capture": left, "fork": right}


def _profiles(db, subject, corpus, as_of, capture, fork, check):
    try:
        left = capture_profile(db, subject, corpus, as_of, capture, check)
        right = fork_profile(db, subject, corpus, as_of, fork, check)
        if left is None or right is None or not compatible(db, left, right, corpus):
            return None
        return left, right
    except (ValueError, TypeError, KeyError, IndexError):
        return None
