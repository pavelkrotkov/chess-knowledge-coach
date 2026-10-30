"""Evidence lineage, replay, failure and consumer integration."""

import pytest

from chess_coach.db import Database
from chess_coach.evidence import evidence_report, validate_evidence
from chess_coach.fact_runs import record_fact_run, record_fact_run_in_transaction
from chess_coach.mapping_runs import record_mapping_run_in_transaction
from chess_coach.mapping_transaction import mapping_transaction
from chess_coach.mastery import mastery_report, update_mastery


@pytest.fixture
def db():
    db = Database(":memory:")
    db.initialize()
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('raw', 'A', 'B', '*')"
    )
    db.connection.execute(
        "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (1, 1, 'fen', '', '')"
    )
    db.connection.commit()
    return db


def fact(db, version="one"):
    return record_fact_run(
        db,
        position_id=1,
        producer="detector",
        detector_version=version,
        input_data={},
        facts=[{"fact_type": "fork", "payload": {}}],
    )


def mapping(db, fact_id, *, producer="one", version="one", value="success", input_data=None):
    items = (
        []
        if fact_id is None
        else [
            {
                "skill": "fork",
                "outcome": value,
                "confidence": 1.0,
                "fact_ids": [fact_id],
                "context": {},
                "observation_at": None,
            }
        ]
    )
    with mapping_transaction(db):
        return record_mapping_run_in_transaction(
            db,
            position_id=1,
            producer=producer,
            mapper_version=version,
            subject="learner",
            operation="execute",
            scope_key="test",
            input_data=input_data or {},
            mappings=items,
        )


def test_replay_replacement_review_and_empty_scope(db):
    source = fact(db)
    first = mapping(db, source["fact_ids"][0])
    evidence_id = first["evidence_ids"][0]
    validate_evidence(db, evidence_id, actor="fixture-reviewer")
    assert mapping(db, source["fact_ids"][0])["evidence_ids"] == [evidence_id]
    assert update_mastery(db, subject="learner", skill="fork", operation="execute") is not None
    second = mapping(db, source["fact_ids"][0], version="two", value="failure")
    assert second["evidence_ids"] != [evidence_id]
    assert (
        db.connection.execute(
            "SELECT human_validated FROM evidence_mappings WHERE id = ?", (evidence_id,)
        ).fetchone()[0]
        == 1
    )
    assert (
        db.connection.execute(
            "SELECT human_validated FROM evidence_mappings WHERE id = ?",
            (second["evidence_ids"][0],),
        ).fetchone()[0]
        == 0
    )
    assert mapping(db, source["fact_ids"][0])["status"] == "superseded"
    assert evidence_report(db)[0]["failure"] == 1
    assert mastery_report(db, subject="learner")[0]["status"] == "insufficient"
    assert (
        update_mastery(db, subject="learner", skill="fork", operation="execute")["status"]
        == "insufficient"
    )
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == 0
    empty = mapping(db, None, version="three")
    assert empty["evidence_ids"] == []
    assert evidence_report(db) == []
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 2


def test_fact_and_mapping_batch_roll_back_together(db):
    old = fact(db)
    mapping(db, old["fact_ids"][0], producer="other")
    with pytest.raises(ValueError), mapping_transaction(db):
        record_fact_run_in_transaction(
            db,
            position_id=1,
            producer="detector",
            detector_version="two",
            input_data={},
            facts=[{"fact_type": "fork", "payload": {}}],
        )
        record_mapping_run_in_transaction(
            db,
            position_id=1,
            producer="test",
            mapper_version="one",
            subject="learner",
            operation="execute",
            scope_key="test",
            input_data={},
            mappings=[
                {
                    "skill": "fork",
                    "outcome": "success",
                    "confidence": 1,
                    "fact_ids": [999],
                    "context": {},
                    "observation_at": None,
                }
            ],
        )
    assert db.connection.execute("SELECT COUNT(*) FROM detector_runs").fetchone()[0] == 1
    assert db.connection.execute("SELECT status FROM detector_runs").fetchone()[0] == "active"
    assert evidence_report(db)[0]["success"] == 1
