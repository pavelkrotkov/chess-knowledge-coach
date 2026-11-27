"""Reconstruct FSRS cards while rejecting invalid legacy values."""

import math
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


def reviewed_card(row, as_of):
    card = card_for(row)
    if card.last_review is None or card.last_review > as_of:
        return None
    if card.stability is None or not 0 < card.stability < math.inf:
        return None
    if card.difficulty is None or not 1 <= card.difficulty <= 10:
        return None
    return card
