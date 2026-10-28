"""Validate terminal completion status and observation timestamps."""

from .mastery_time import parse_utc


def terminal_lineage(row, evidence) -> bool:
    if row["hints_used"] != 0 or row["hint_events"] != 0 or row["event_kind"] != "move":
        return False
    expected = {
        "success": ("solved", "verified_mate_in_one"),
        "failure": ("failed", "missed_mate_in_one"),
    }
    if expected.get(evidence["outcome"]) != (row["status"], row["evidence_reason"]):
        return False
    observed = parse_utc(evidence["observation_at"])
    return observed is not None and all(
        parse_utc(row[key]) == observed
        for key in ("finished_at", "created_at", "reviewed_at", "event_time")
    )
