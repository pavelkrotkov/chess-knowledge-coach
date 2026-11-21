"""Build descriptive profile summaries from one bounded ordered sample."""

from .opening_profile_center import summarize as center_summary
from .opening_profile_summary import summarize


def summarize_profile(db, rows, parent, move, extended):
    summary = summarize(db, rows)
    if extended:
        from .opening_profile_extended import summarize as extended_summary

        summary.update(extended_summary(db, rows))
    summary["center"] = center_summary(db, rows, parent, move)
    return summary
