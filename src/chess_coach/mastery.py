"""Recompute transparent mastery estimates from eligible reviewed evidence."""

from datetime import datetime
from typing import Any

from .db import Database
from .mapping_transaction import mapping_transaction
from .mastery_eligibility import eligible_contexts
from .mastery_policy import HALF_LIFE_DAYS, MIN_CONTEXTS, POLICY_VERSION, calculate
from .mastery_report import mastery_report
from .mastery_storage import write_state
from .mastery_time import as_utc

MASTERY_MODEL_VERSION = POLICY_VERSION
__all__ = ["mastery_report", "update_mastery"]


def update_mastery(
    db: Database,
    *,
    skill: str,
    operation: str,
    subject: str = "default",
    as_of: datetime | None = None,
) -> dict[str, Any]:
    subject = subject.strip().casefold()
    now = as_utc(as_of)
    with mapping_transaction(db):
        items, exclusions = eligible_contexts(db, subject, skill, operation, now)
        values = calculate(items)
        state = db.connection.execute(
            "SELECT * FROM mastery_states WHERE subject = ? AND skill = ? AND operation = ?",
            (subject, skill, operation),
        ).fetchone()
        result = {
            **values,
            "subject": subject,
            "skill": skill,
            "operation": operation,
            "policy_version": POLICY_VERSION,
            "as_of": now.isoformat(),
            "half_life_days": HALF_LIFE_DAYS,
            "minimum_contexts": MIN_CONTEXTS,
            "horizon_days": 365,
            "heuristic": True,
            "exclusions": exclusions,
            "training_context_supported": False,
        }
        if values["status"] == "insufficient":
            if state is not None:
                db.connection.execute(
                    "UPDATE mastery_states SET is_stale = 1 WHERE id = ?", (state["id"],)
                )
        else:
            saved = write_state(db, subject, skill, operation, state, values, POLICY_VERSION, now)
            result["id"] = saved["id"]
        return result
