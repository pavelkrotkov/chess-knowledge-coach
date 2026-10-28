"""Apply one validated FSRS review within a caller-owned transaction."""

from datetime import UTC, datetime

from fsrs import Scheduler

from .db import Database
from .training_card import card_for
from .training_scheduler import RATINGS, duration_ms, scheduler_config, utc
from .training_storage import store_review


def review_item_in_transaction(
    db: Database,
    item_id: int,
    rating: str,
    *,
    elapsed_seconds: int | None = None,
    reviewed_at: datetime | None = None,
) -> dict[str, object]:
    if not db.connection.in_transaction:
        raise RuntimeError("scheduling requires a transaction")
    if rating not in RATINGS:
        raise ValueError("rating must be again, hard, good, or easy")
    duration = duration_ms(elapsed_seconds)
    now = utc(reviewed_at if reviewed_at is not None else datetime.now(UTC))
    row = db.connection.execute("SELECT * FROM training_items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise ValueError(f"unknown training item: {item_id}")
    card = card_for(row)
    if card.last_review is not None and now < card.last_review:
        raise ValueError("review timestamp cannot precede the previous review")
    scheduler = Scheduler(enable_fuzzing=False)
    updated, _ = scheduler.review_card(
        card, RATINGS[rating], review_datetime=now, review_duration=duration
    )
    return store_review(
        db, item_id, rating, elapsed_seconds, now, updated, scheduler_config(scheduler)
    )
