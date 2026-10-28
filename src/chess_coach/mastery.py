"""Evidence-gated, deliberately simple mastery states."""

from datetime import UTC, datetime, timedelta
from typing import Any

from .db import Database
from .mastery_report import mastery_report
from .mastery_scores import _observation_time, _score
from .mastery_storage import write_state

MASTERY_MODEL_VERSION = "weighted-outcomes-v1"
__all__ = ["mastery_report", "update_mastery"]


def update_mastery(
    db: Database, *, skill: str, operation: str, subject: str = "default"
) -> dict[str, Any] | None:
    rows = db.connection.execute(
        """SELECT e.id, e.outcome, e.confidence, e.context_json, e.observation_at
        FROM evidence_mappings e LEFT JOIN mapping_runs r ON r.id = e.mapping_run_id
        WHERE e.subject = ? AND e.skill = ? AND e.operation = ? AND e.human_validated = 1
        AND (e.mapping_run_id IS NULL OR r.status = 'active') ORDER BY e.id""",
        (subject, skill, operation),
    ).fetchall()
    state = db.connection.execute(
        "SELECT * FROM mastery_states WHERE subject = ? AND skill = ? AND operation = ?",
        (subject, skill, operation),
    ).fetchone()
    if not rows:
        if state is not None:
            db.connection.execute(
                "UPDATE mastery_states SET is_stale = 1 WHERE id = ?", (state["id"],)
            )
            db.connection.commit()
        return None
    values = _calculate(rows)
    return write_state(db, subject, skill, operation, state, values, MASTERY_MODEL_VERSION)


def _calculate(rows) -> dict:
    mastery, weight = _score(rows)
    cutoff = datetime.now(UTC) - timedelta(days=30)
    recent, older = _partition(rows, cutoff)
    recent_score, _ = _score(recent)
    older_score, older_weight = _score(older)
    return {
        "mastery": mastery,
        "evidence_weight": weight,
        "uncertainty": 1 / (1 + weight),
        "trend_30d": recent_score - older_score if older_weight else 0.0,
        "evidence_ids": [int(row["id"]) for row in rows],
    }


def _partition(rows, cutoff):
    recent, older = [], []
    for row in rows:
        observed = _observation_time(row)
        if observed is not None:
            (recent if observed >= cutoff else older).append(row)
    return recent, older
