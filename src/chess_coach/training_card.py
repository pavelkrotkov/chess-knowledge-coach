"""Reconstruct FSRS cards while rejecting invalid legacy values."""

from datetime import datetime

from fsrs import Card, State

from .training_scheduler import utc


def card_for(row) -> Card:
    try:
        state = State[row["state"].capitalize()]
    except (KeyError, AttributeError) as exc:
        raise ValueError(f"invalid training item state: {row['state']}") from exc
    try:
        due = utc(datetime.fromisoformat(row["due"]))
        last = utc(datetime.fromisoformat(row["last_review"])) if row["last_review"] else None
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid training item timestamp for item {row['id']}") from exc
    return Card(
        card_id=row["id"],
        state=state,
        step=row["step"],
        stability=row["stability"],
        difficulty=row["difficulty"],
        due=due,
        last_review=last,
    )
