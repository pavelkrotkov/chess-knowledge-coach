"""Validate immutable recognition timing and categorical responses."""

from .mastery_time import parse_utc


def validate(row):
    if not _ordered(row) or not _response(row):
        raise ValueError("recognition event unavailable")


def _ordered(row):
    started, answered = parse_utc(row["started_at"]), parse_utc(row["answered_at"])
    return bool(
        started
        and answered
        and started.isoformat() == row["started_at"]
        and answered.isoformat() == row["answered_at"]
        and answered >= started
    )


def _response(row):
    if row["action"] == "answer":
        return row["assisted"] == 0 and row["answer"] in {"capture", "mate", "uncertain"}
    return row["action"] == "reveal" and row["assisted"] == 1 and row["answer"] is None


def outcome(row, kind):
    if row["action"] == "reveal":
        return "revealed"
    if row["answer"] == "uncertain":
        return "uncertain"
    return "verified" if row["answer"] == kind else "incorrect"
