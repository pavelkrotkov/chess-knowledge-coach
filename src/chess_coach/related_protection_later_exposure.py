"""Fail closed if a prompt was re-exposed before its first legal answer."""

from .learner_identity import normalize_identity
from .mastery_time import parse_utc
from .puzzle_session_validate import validate_line
from .related_capture_familiar import LIMIT
from .related_capture_position import prompt_key


def require_unexposed(db, row, key, check):
    prefix = key + " "
    rows = db.connection.execute(
        """SELECT attempt_id,subject FROM unified_sessions
        WHERE prompt_fen>=? AND prompt_fen<? AND attempt_id<>? LIMIT ?""",
        (prefix, prefix + "\uffff", row["attempt_id"], LIMIT + 1),
    ).fetchall()
    if len(rows) > LIMIT:
        raise ValueError("protection encounter coverage unavailable")
    subject = normalize_identity(row["subject"])
    for other in rows:
        check()
        if normalize_identity(other["subject"]) == subject:
            raise ValueError("protection assessment was re-exposed")
    _legacy(db, row, key, check)


def _legacy(db, row, key, check):
    started = parse_utc(row["started_at"])
    if started is None:
        raise ValueError("protection assessment time unavailable")
    rows = db.connection.execute(
        """SELECT initial_fen,solution,started_at FROM puzzle_sessions
        WHERE julianday(started_at)>=julianday(?) OR julianday(started_at) IS NULL
        LIMIT ?""",
        (row["started_at"], LIMIT + 1),
    ).fetchall()
    if len(rows) > LIMIT:
        raise ValueError("protection encounter coverage unavailable")
    for other in rows:
        check()
        if prompt_key(validate_line(other["initial_fen"], other["solution"])) != key:
            continue
        when = parse_utc(other["started_at"])
        if when is None or when >= started:
            raise ValueError("protection assessment was re-exposed")
