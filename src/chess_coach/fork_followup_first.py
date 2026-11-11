"""Find the first normalized prompt encounter under the caller's deadline."""

from .mastery_time import parse_utc
from .related_capture_position import prompt_key


def first(db, subject, row):
    prefix = prompt_key(row["prompt_fen"]) + " "
    matches = db.connection.execute(
        """SELECT attempt_id,started_at FROM unified_sessions
        WHERE subject=? AND prompt_fen>=? AND prompt_fen<?
        ORDER BY started_at,attempt_id LIMIT 2""",
        (subject, prefix, prefix + "\uffff"),
    ).fetchall()
    if not matches or matches[0]["attempt_id"] != row["attempt_id"]:
        raise ValueError("fork assessment is not a first encounter")
    when = parse_utc(matches[0]["started_at"])
    if when is None or when.isoformat() != matches[0]["started_at"]:
        raise ValueError("fork assessment time unavailable")
    if len(matches) > 1 and matches[1]["started_at"] == matches[0]["started_at"]:
        raise ValueError("fork assessment order unavailable")
