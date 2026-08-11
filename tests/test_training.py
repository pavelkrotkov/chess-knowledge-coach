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


def test_training_item_creation_is_idempotent_and_rejects_negative_elapsed(tmp_path) -> None:
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    first = create_training_item(
        db, source_type="canonical", source_ref="fen", skill="fork", operation="execute"
    )
    second = create_training_item(
        db, source_type="canonical", source_ref="fen", skill="fork", operation="execute"
    )

    assert first == second
    try:
        review_item(db, first, "good", elapsed_seconds=-1)
    except ValueError as exc:
        assert "non-negative" in str(exc)
    else:
        raise AssertionError("negative elapsed time was accepted")


def test_review_rejects_corrupt_state_and_due_timestamp(tmp_path) -> None:
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    item_id = create_training_item(
        db, source_type="puzzle", source_ref="p1", skill="fork", operation="execute"
    )
    db.connection.execute("UPDATE training_items SET state = 'corrupt' WHERE id = ?", (item_id,))
    db.connection.commit()
    try:
        review_item(db, item_id, "good")
    except ValueError as exc:
        assert "invalid training item state" in str(exc)
    else:
        raise AssertionError("corrupt state was accepted")
