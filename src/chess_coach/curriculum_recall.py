"""Read an authoritative item's compatible scheduler estimate without reviewing it."""

import json
import math

from fsrs import Scheduler

from .fact_fingerprint import canonical
from .training_card import reviewed_card
from .training_scheduler import SCHEDULER_VERSION, scheduler_config


def estimate(db, selected, as_of):
    row = db.connection.execute(
        "SELECT * FROM training_items WHERE id=?", (selected["id"],)
    ).fetchone()
    value = None
    if row is not None and all(
        row[key] == selected[key] for key in ("source_type", "source_ref", "due")
    ):
        value = _compatible(row, as_of)
    return {
        "status": "estimated" if value is not None else "unknown",
        "probability": value,
        "as_of": as_of.isoformat(),
    }


def _compatible(row, as_of):
    try:
        scheduler = Scheduler(enable_fuzzing=False)
        if row["scheduler_version"] != SCHEDULER_VERSION:
            return None
        if canonical(json.loads(row["scheduler_config_json"])) != canonical(
            scheduler_config(scheduler)
        ):
            return None
        card = reviewed_card(row, as_of)
        if card is None:
            return None
        value = scheduler.get_card_retrievability(card, current_datetime=as_of)
        return value if math.isfinite(value) and 0 <= value <= 1 else None
    except (ValueError, TypeError, OverflowError, KeyError, IndexError, AttributeError):
        return None
