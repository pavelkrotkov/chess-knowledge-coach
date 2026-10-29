import sqlite3

import pytest

from chess_coach.classification_schema import add_classification_lineage
from chess_coach.db import SCHEMA, Database
from chess_coach.evidence_review_schema import add_evidence_reviews
from chess_coach.evidence_schema import add_evidence_lineage
from chess_coach.fact_schema import add_fact_lineage
from chess_coach.lichess_schema import add_sync_turn
from chess_coach.puzzle_session_schema import add_puzzle_sessions


def legacy_db():
    db = Database(":memory:")
    db.connection.executescript(SCHEMA)
    add_sync_turn(db.connection)
    add_puzzle_sessions(db.connection)
    add_fact_lineage(db.connection)
    add_evidence_lineage(db.connection)
    add_classification_lineage(db.connection)
    add_evidence_reviews(db.connection)
    db.connection.execute(
        """INSERT INTO mastery_states
        (id, subject, skill, operation, mastery, uncertainty, evidence_weight, trend_30d,
         updated_at, model_version, is_stale)
        VALUES (7, 'fixture', 'fork', 'execute', .7, .2, 4, .1, 'old', 'v1', 0)"""
    )
    db.connection.execute(
        """INSERT INTO mastery_events
        (id, state_id, evidence_ids_json, previous_mastery, new_mastery, changed_at, model_version)
        VALUES (11, 7, '[1]', NULL, .7, 'old', 'v1')"""
    )
    db.connection.execute("CREATE INDEX mastery_custom_index ON mastery_states(updated_at)")
    db.connection.execute("PRAGMA user_version = 9")
    db.connection.commit()
    return db


def test_v9_upgrade_preserves_mastery_identity_history_and_nullable_trend() -> None:
    db = legacy_db()
    before_state = tuple(db.connection.execute("SELECT * FROM mastery_states").fetchone())
    before_event = tuple(db.connection.execute("SELECT * FROM mastery_events").fetchone())
    db.initialize()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 25
    assert tuple(db.connection.execute("SELECT * FROM mastery_states").fetchone()) == before_state
    assert tuple(db.connection.execute("SELECT * FROM mastery_events").fetchone()) == before_event
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'index' AND name = 'mastery_custom_index'"
        ).fetchone()[0]
        == 1
    )
    db.connection.execute("UPDATE mastery_states SET trend_30d = NULL WHERE id = 7")
    db.connection.commit()
    assert db.connection.execute("SELECT trend_30d FROM mastery_states").fetchone()[0] is None
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(sqlite3.IntegrityError):
        db.connection.execute(
            "INSERT INTO mastery_events(state_id,evidence_ids_json,new_mastery,changed_at,model_version) "
            "VALUES (999, '[]', .5, 'test', 'test')"
        )


def test_external_mastery_reference_fails_without_modification() -> None:
    db = legacy_db()
    db.connection.execute(
        "CREATE TABLE external_history (state_id INTEGER REFERENCES mastery_states(id) ON DELETE CASCADE)"
    )
    db.connection.execute("INSERT INTO external_history VALUES (7)")
    db.connection.commit()
    with pytest.raises(RuntimeError, match="external state references"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 9
    assert db.connection.execute("SELECT id FROM mastery_events").fetchone()[0] == 11
    assert db.connection.execute("SELECT state_id FROM external_history").fetchone()[0] == 7


def test_mastery_migration_failure_rolls_back_tables_and_history(monkeypatch) -> None:
    from chess_coach import db_recent
    from chess_coach.mastery_schema import allow_unknown_trend

    db = legacy_db()

    def fail_after_copy(connection):
        allow_unknown_trend(connection)
        raise RuntimeError("injected migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "allow_unknown_trend", fail_after_copy)
        with pytest.raises(RuntimeError, match="injected migration failure"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 9
    assert db.connection.execute("SELECT id FROM mastery_states").fetchone()[0] == 7
    assert db.connection.execute("SELECT id FROM mastery_events").fetchone()[0] == 11
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE name IN ('mastery_states_new', 'mastery_events_new')"
        ).fetchone()[0]
        == 0
    )


def test_v10_to_v11_preserves_scheduler_configuration_and_history() -> None:
    from chess_coach.training_schema import add_training_scheduler_config

    db = legacy_db()
    add_training_scheduler_config(db.connection)
    db.connection.execute("""INSERT INTO training_items
        (source_type,source_ref,skill,operation,due,scheduler_version,scheduler_config_json)
        VALUES (\"puzzle\",\"fixture\",\"fork\",\"execute\",\"2026-01-01\",\"v1\",\"config\")""")
    db.connection.execute("""INSERT INTO training_attempts
        (item_id,rating,reviewed_at,scheduler_version,scheduler_config_json)
        VALUES (1,\"good\",\"2026-01-01\",\"v1\",\"config\")""")
    db.connection.execute("PRAGMA user_version = 10")
    db.connection.commit()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 25
    assert (
        db.connection.execute("SELECT scheduler_config_json FROM training_items").fetchone()[0]
        == "config"
    )
    assert (
        db.connection.execute("SELECT scheduler_config_json FROM training_attempts").fetchone()[0]
        == "config"
    )
    assert db.connection.execute("SELECT id FROM mastery_events").fetchone()[0] == 11
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
