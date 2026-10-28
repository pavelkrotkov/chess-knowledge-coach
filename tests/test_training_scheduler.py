"""Scheduler provenance, time handling and transaction behavior."""

import json
from datetime import UTC, datetime, timedelta, timezone

import pytest
from fsrs import Scheduler

from chess_coach.db import Database
from chess_coach.training import (
    SCHEDULER_VERSION,
    create_training_item,
    due_items,
    review_item,
    review_item_in_transaction,
)


@pytest.fixture
def item():
    db = Database(":memory:")
    db.initialize()
    item_id = create_training_item(
        db, source_type="puzzle", source_ref="synthetic", skill="fork", operation="execute"
    )
    return db, item_id


def test_seconds_are_passed_as_milliseconds_and_utc_normalized(item, monkeypatch):
    db, item_id = item
    calls = []
    original = Scheduler.review_card

    def capture(self, card, rating, *, review_datetime=None, review_duration=None):
        calls.append((review_datetime, review_duration))
        return original(
            self, card, rating, review_datetime=review_datetime, review_duration=review_duration
        )

    monkeypatch.setattr(Scheduler, "review_card", capture)
    when = datetime(2025, 2, 1, 12, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    result = review_item(db, item_id, "good", elapsed_seconds=12, reviewed_at=when)
    assert calls == [(datetime(2025, 2, 1, 7, 0, tzinfo=UTC), 12000)]
    assert calls[0][0].tzinfo is UTC
    attempt = db.connection.execute("SELECT * FROM training_attempts").fetchone()
    current = db.connection.execute("SELECT * FROM training_items").fetchone()
    assert attempt["elapsed_seconds"] == 12
    assert attempt["reviewed_at"] == "2025-02-01T07:00:00+00:00"
    assert attempt["scheduler_version"] == current["scheduler_version"] == SCHEDULER_VERSION
    assert json.loads(attempt["scheduler_config_json"]) == json.loads(
        current["scheduler_config_json"]
    )
    assert result["attempt_id"] == attempt["id"]
    config = json.loads(attempt["scheduler_config_json"])
    scheduler = Scheduler(enable_fuzzing=False)
    assert config["parameters"] == list(scheduler.parameters)
    assert config["desired_retention"] == scheduler.desired_retention
    assert config["learning_steps_seconds"] == [
        step.total_seconds() for step in scheduler.learning_steps
    ]
    assert config["relearning_steps_seconds"] == [
        step.total_seconds() for step in scheduler.relearning_steps
    ]
    assert config["maximum_interval"] == scheduler.maximum_interval
    assert config["enable_fuzzing"] is False


def test_unknown_duration_stays_unknown(item, monkeypatch):
    db, item_id = item
    calls = []
    original = Scheduler.review_card

    def capture(self, card, rating, *, review_datetime=None, review_duration=None):
        calls.append(review_duration)
        return original(
            self, card, rating, review_datetime=review_datetime, review_duration=review_duration
        )

    monkeypatch.setattr(Scheduler, "review_card", capture)
    review_item(db, item_id, "good")
    assert calls == [None]
    assert (
        db.connection.execute("SELECT elapsed_seconds FROM training_attempts").fetchone()[0] is None
    )


@pytest.mark.parametrize("invalid", [-1, 1.5, True, float("inf"), float("nan"), "12", 2**63])
def test_invalid_duration_does_not_change_state(item, invalid):
    db, item_id = item
    before = tuple(db.connection.execute("SELECT * FROM training_items").fetchone())
    with pytest.raises(ValueError, match="elapsed_seconds"):
        review_item(db, item_id, "good", elapsed_seconds=invalid)
    assert tuple(db.connection.execute("SELECT * FROM training_items").fetchone()) == before
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0


def test_naive_and_backward_timestamps_are_rejected_atomically(item):
    db, item_id = item
    with pytest.raises(ValueError, match="timezone-aware"):
        review_item(db, item_id, "good", reviewed_at=datetime(2025, 1, 1))
    with pytest.raises(ValueError, match="timezone-aware"):
        due_items(db, now=datetime(2025, 1, 1))
    when = datetime(2025, 1, 1, tzinfo=UTC)
    review_item(db, item_id, "good", reviewed_at=when)
    before = tuple(db.connection.execute("SELECT * FROM training_items").fetchone())
    with pytest.raises(ValueError, match="previous review"):
        review_item(db, item_id, "good", reviewed_at=when - timedelta(seconds=1))
    assert tuple(db.connection.execute("SELECT * FROM training_items").fetchone()) == before
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 1


def test_owned_transaction_and_injected_failure_roll_back(item, monkeypatch):
    from chess_coach import training_review

    db, item_id = item
    with pytest.raises(RuntimeError, match="requires a transaction"):
        review_item_in_transaction(db, item_id, "good")
    db.connection.execute("UPDATE training_items SET source_ref='pending' WHERE id=?", (item_id,))
    review_item(db, item_id, "good")
    assert db.connection.in_transaction
    db.connection.rollback()
    assert (
        db.connection.execute("SELECT source_ref FROM training_items").fetchone()[0] == "synthetic"
    )
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0

    before = tuple(db.connection.execute("SELECT * FROM training_items").fetchone())
    original = training_review.store_review

    def fail(*args):
        original(*args)
        raise RuntimeError("injected failure")

    monkeypatch.setattr(training_review, "store_review", fail)
    with pytest.raises(RuntimeError, match="injected failure"):
        review_item(db, item_id, "good")
    assert tuple(db.connection.execute("SELECT * FROM training_items").fetchone()) == before
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0


def test_composable_review_returns_id_and_leaves_transaction_to_caller(item):
    db, item_id = item
    db.connection.execute("BEGIN")
    result = review_item_in_transaction(db, item_id, "good")
    assert db.connection.in_transaction
    assert (
        db.connection.execute("SELECT id FROM training_attempts").fetchone()[0]
        == result["attempt_id"]
    )
    db.connection.rollback()
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0


def test_existing_item_config_is_not_invented_on_recreate(item):
    db, item_id = item
    db.connection.execute(
        "UPDATE training_items SET scheduler_config_json=NULL, scheduler_version='legacy'"
    )
    db.connection.commit()
    assert (
        create_training_item(
            db, source_type="puzzle", source_ref="synthetic", skill="fork", operation="execute"
        )
        == item_id
    )
    row = db.connection.execute(
        "SELECT scheduler_version,scheduler_config_json FROM training_items"
    ).fetchone()
    assert tuple(row) == ("legacy", None)
    review_item(db, item_id, "good")
    row = db.connection.execute(
        "SELECT scheduler_version,scheduler_config_json FROM training_items"
    ).fetchone()
    assert row[0] == SCHEDULER_VERSION and json.loads(row[1])["enable_fuzzing"] is False


def test_schema_upgrade_leaves_legacy_configuration_unknown(monkeypatch):
    from chess_coach import db_recent

    db = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_training_scheduler_config", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=9")
    db.connection.execute("""INSERT INTO training_items
        (source_type,source_ref,skill,operation,due,scheduler_version)
        VALUES ('legacy','source','fork','execute','2024-01-01T00:00:00+00:00','old')""")
    db.connection.execute("""INSERT INTO training_attempts(item_id,rating,reviewed_at,scheduler_version)
        VALUES (1,'good','2024-01-01T00:00:00+00:00','old')""")
    db.connection.commit()
    db.initialize()
    assert (
        db.connection.execute("SELECT scheduler_config_json FROM training_items").fetchone()[0]
        is None
    )
    assert (
        db.connection.execute("SELECT scheduler_config_json FROM training_attempts").fetchone()[0]
        is None
    )
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_schema_upgrade_failure_is_atomic(monkeypatch):
    from chess_coach import db_recent

    db = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_training_scheduler_config", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=9")
    db.connection.commit()
    original = db_recent.add_training_scheduler_config

    def fail(connection):
        original(connection)
        raise RuntimeError("injected migration failure")

    monkeypatch.setattr(db_recent, "add_training_scheduler_config", fail)
    with pytest.raises(RuntimeError, match="injected migration failure"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 9
    assert "scheduler_config_json" not in {
        row[1] for row in db.connection.execute("PRAGMA table_info(training_items)")
    }
