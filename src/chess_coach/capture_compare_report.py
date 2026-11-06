"""Compare two bounded, fully verified unassisted capture cohorts."""

from .capture_compare_samples import comparison
from .capture_compare_select import select
from .mate_assessment_compare import SAMPLE


def report(db, subject, corpus):
    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    groups, limited, unmatched = select(db, subject, corpus)
    eligible = [group for group in groups if len(group) >= 2 * SAMPLE]
    output = {
        "limited": limited,
        "unmatched": unmatched,
        "largest": max((len(group) for group in groups), default=0),
        "status": "sparse",
    }
    if limited:
        output["status"] = "incomplete"
    elif eligible:
        group = max(eligible, key=lambda value: value[-1][0]["started_at"])
        output.update(comparison(db, group, corpus))
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != before:
        raise ValueError("capture comparison changed")
    return output
