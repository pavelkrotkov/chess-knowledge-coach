"""Nominate a real next harder band from bounded related-session history."""

from .capture_certificate_reference import session_marker
from .capture_certificate_reference_page import session
from .capture_certificate_related import related_reference
from .capture_difficulty import checked


def context(db, subject, progress, check):
    check()
    row, marker = session(db, subject, session_marker(progress.get("harder")))
    progress["harder"] = marker
    if row is None:
        return None, False
    check()
    if (row["source_type"], row["objective"]) != ("corpus", "capture_named_target"):
        return None, True
    reference = related_reference(row, subject)
    if reference is None:
        return None, True
    try:
        difficulty = checked(
            db,
            subject,
            row["source_version"],
            reference["related"]["position_id"],
            row["attempt_id"],
            check,
        )
    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
        return None, True
    version = row["source_version"]
    return {
        "lower": difficulty["band"],
        "upper": difficulty["band"] + 199,
        "last": "",
        "ceiling": version,
        "preferred": version,
        "first": True,
        "harder": True,
    }, True
