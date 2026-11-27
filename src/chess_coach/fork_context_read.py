"""Read one fork profile against a stable private artifact snapshot."""

import sqlite3

from .curriculum_capture_inputs import observe
from .fork_capture_comparison import compare
from .fork_context_profile import profile
from .fork_game_trend_paths import location as trend_location
from .fork_game_trend_report import report as trend_report
from .fork_miss_store import location as miss_location
from .opening_study_source import fingerprint


def read(db, subject, corpus, root, as_of, check):
    try:
        before = observe(db, subject, root, check)
        paths = [trend_location(db, root), miss_location(db, root)]
        if any(path is None for path in paths):
            raise ValueError("fork artifact scope unavailable")
        files = fingerprint(paths)
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return trend_report(db, subject, root, check=check, as_of=as_of)
    try:
        result = trend_report(db, subject, root, check=check, as_of=as_of)
        if not result:
            return None
        value = profile(db, subject, corpus, as_of, result, check)
        common = compare(db, subject, corpus, root, as_of, result, check)
        if observe(db, subject, root, check) != before or fingerprint(paths) != files:
            return None
        result["context_profile"] = value
        result["common_comparison"] = common
        return result
    except (OSError, sqlite3.Error, ValueError, TypeError, KeyError, IndexError):
        return None
