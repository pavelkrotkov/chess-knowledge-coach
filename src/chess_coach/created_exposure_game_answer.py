"""Find one current, unassisted first answer for the selected profile."""

import json
import sqlite3
import time

from .capture_plan_result import result as inspect_result
from .created_exposure_game_result import valid
from .mastery_time import parse_utc
from .mate_assessment_events import replay as replay_events
from .objective_created_contract import GOAL
from .related_created_contract import KEY

# Limit recent sessions; absence from this bounded history is not proof of no answer.
LIMIT = 32


def _answer(db, row):
    observed = replay_events(db, row)
    result = inspect_result(db, row, observed, matcher=valid)
    answer, start = parse_utc(result.get("answered_at")), parse_utc(row["started_at"])
    if (
        result["status"] not in {"correct", "incorrect"}
        or not answer
        or not start
        or answer < start
    ):
        raise ValueError("answer unavailable")
    return {"attempt": row["attempt_id"], "answered_at": result["answered_at"]}


def first_answer(db, learner, profile, deadline):
    rows = db.connection.execute(
        """SELECT * FROM unified_sessions INDEXED BY idx_unified_sessions_subject
        WHERE subject=? AND source_type='corpus' AND objective=?
        ORDER BY started_at DESC,attempt_id LIMIT ?""",
        (learner, GOAL, LIMIT),
    ).fetchall()
    for row in rows:
        if time.monotonic() >= deadline:
            break
        try:
            data = json.loads(row["provenance_json"])
            if data[KEY]["evidence_id"] == profile["evidence_id"]:
                return _answer(db, row)
        except (ValueError, TypeError, KeyError, IndexError, sqlite3.Error, StopIteration):
            continue
    return None


def follows(date, answer):
    """Determine each window separately; a missing date is not an overlap."""
    start = parse_utc(date)
    end = parse_utc(answer)
    return start > end if start and end else None
