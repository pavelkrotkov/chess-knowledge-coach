from datetime import UTC, datetime

from chess_coach.db import Database
from chess_coach.training import create_training_item, due_items, review_item


def test_fsrs_reviews_schedule_training_items(tmp_path) -> None:
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    item_id = create_training_item(
        db,
        source_type="puzzle",
        source_ref="p1",
        skill="fork",
        operation="execute",
    )
    now = datetime.now(UTC)

    assert len(due_items(db, now=now)) == 1
    reviewed = review_item(db, item_id, "good", elapsed_seconds=12, reviewed_at=now)

    assert reviewed["state"] == "learning"
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 1
    assert due_items(db, now=now) == []
