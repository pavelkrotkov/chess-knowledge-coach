"""Validate selected first and recent capture samples."""

from .capture_compare_chronology import answer_end
from .capture_compare_verify import verify
from .mate_assessment_compare import SAMPLE, comparable, ordered
from .mate_assessment_group_counts import counts


def _unassisted(entries):
    return all(entry.get("hints") == 0 and entry.get("reveals") == 0 for entry in entries)


def comparison(db, group, corpus):
    result = {
        "status": "unavailable",
        "checked": 0,
        "group_size": len(group),
        "rating_start": group[0][1]["rating_start"],
    }
    if not ordered([row for row, _ in group]):
        result["reason"] = "ambiguous_boundary"
        return result
    chosen = group[:SAMPLE] + group[-SAMPLE:]
    entries, complete = verify(db, [row for row, _ in chosen], corpus)
    result["checked"] = len(entries)
    if complete:
        result.update(earlier=counts(entries[:SAMPLE]), later=counts(entries[-SAMPLE:]))
        if comparable(entries, False) and _unassisted(entries):
            result["status"] = "comparable"
            result["answer_end"] = answer_end(entries)
    return result
