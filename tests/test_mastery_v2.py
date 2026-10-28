from datetime import UTC, datetime, timedelta

import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.fact_runs import record_fact_run
from chess_coach.ingest import ingest_pgn
from chess_coach.mapping_runs import record_mapping_run_in_transaction
from chess_coach.mapping_transaction import mapping_transaction
from chess_coach.mastery import mastery_report, update_mastery

NOW = datetime(2026, 10, 1, 12, tzinfo=UTC)


def add_game(db, number, age, outcome="success", ply=1, subject="learner", producer="detector"):
    when = NOW - timedelta(days=age)
    pgn = f"""[Event "Synthetic {number}"]
[White "Learner"]
[Black "Opponent"]
[Result "1-0"]
[UTCDate "{when:%Y.%m.%d}"]
[UTCTime "{when:%H:%M:%S}"]

1. e4 e5 2. Nf3 Nc6 1-0
"""
    ingest_pgn(db, pgn)
    game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
    position_id = db.connection.execute(
        "SELECT id FROM positions WHERE game_id = ? AND ply = ?", (game_id, ply)
    ).fetchone()[0]
    facts = record_fact_run(
        db,
        position_id=position_id,
        producer=producer,
        detector_version="v1",
        input_data={},
        facts=[{"fact_type": "fork", "payload": {}}],
    )
    with mapping_transaction(db):
        mapped = record_mapping_run_in_transaction(
            db,
            position_id=position_id,
            producer=producer,
            mapper_version="v1",
            subject=subject,
            operation="execute",
            scope_key="fixture",
            input_data={},
            mappings=[
                {
                    "skill": "fork",
                    "outcome": outcome,
                    "confidence": 1,
                    "fact_ids": facts["fact_ids"],
                    "context": {"claimed_origin": "other"},
                    "observation_at": when.isoformat(),
                }
            ],
        )
    evidence_id = mapped["evidence_ids"][0]
    review_evidence(db, evidence_id, decision="accept", actor="fixture-reviewer")
    return evidence_id


def setup_db():
    db = Database(":memory:")
    db.initialize()
    return db


def test_weighted_policy_as_of_and_revoke_invalidates_state():
    db = setup_db()
    ids = [add_game(db, 1, 0), add_game(db, 2, 90, "failure"), add_game(db, 3, 180)]
    result = update_mastery(db, subject="learner", skill="fork", operation="execute", as_of=NOW)
    assert result["status"] == "sufficient"
    assert result["mastery"] == pytest.approx(1.25 / 1.75)
    assert result["effective_weight"] == pytest.approx(1.75)
    assert result["uncertainty"] == pytest.approx(1 / 2.75)
    assert result["trend_30d"] == pytest.approx(1 - 0.25 / 0.75)
    assert result["supporting_evidence_ids"] == ids
    assert result["heuristic"] is True
    assert len(mastery_report(db, subject="learner", as_of=NOW)) == 1
    assert db.connection.execute("SELECT count(*) FROM mastery_events").fetchone()[0] == 1
    review_evidence(db, ids[0], decision="revoke", actor="fixture-reviewer")
    report = mastery_report(db, subject="learner", as_of=NOW)[0]
    assert report["status"] == "insufficient"
    assert report["mastery"] is None and report["trend_30d"] is None
    assert report["exclusions"]["revoked"] == 1
    assert db.connection.execute("SELECT is_stale FROM mastery_states").fetchone()[0] == 1
    assert db.connection.execute("SELECT count(*) FROM mastery_events").fetchone()[0] == 1


def test_horizon_future_learner_ownership_and_null_trend():
    db = setup_db()
    add_game(db, 1, 365)
    add_game(db, 2, 366)
    add_game(db, 3, -1)
    add_game(db, 4, 5, ply=2)
    add_game(db, 5, 4)
    add_game(db, 6, 3)
    result = update_mastery(db, subject="learner", skill="fork", operation="execute", as_of=NOW)
    assert result["context_count"] == 3
    assert result["exclusions"] == {
        "future_observation": 1,
        "not_learner_decision": 1,
        "outside_horizon": 1,
    }
    assert result["trend_30d"] == 0
    with pytest.raises(ValueError):
        update_mastery(
            db, subject="learner", skill="fork", operation="execute", as_of=NOW.replace(tzinfo=None)
        )
    newer = mastery_report(db, subject="learner", as_of=NOW + timedelta(days=366))[0]
    assert newer["status"] == "insufficient"


def test_nullable_trend_and_atomic_rollback():
    db = setup_db()
    for i in range(3):
        add_game(db, i, i)
    db.connection.execute(
        'CREATE TRIGGER fail_event BEFORE INSERT ON mastery_events BEGIN SELECT RAISE(ABORT, "blocked"); END'
    )
    db.connection.commit()
    with pytest.raises(Exception, match="blocked"):
        update_mastery(db, subject="learner", skill="fork", operation="execute", as_of=NOW)
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
    db.connection.execute("DROP TRIGGER fail_event")
    db.connection.commit()
    result = update_mastery(db, subject="learner", skill="fork", operation="execute", as_of=NOW)
    assert result["trend_30d"] is None
    assert db.connection.execute("SELECT trend_30d FROM mastery_states").fetchone()[0] is None
    with pytest.raises(RuntimeError), mapping_transaction(db):
        update_mastery(
            db,
            subject="learner",
            skill="fork",
            operation="execute",
            as_of=NOW + timedelta(days=1),
        )
        raise RuntimeError("abort enclosing work")
    assert db.connection.execute("SELECT count(*) FROM mastery_events").fetchone()[0] == 1


def test_multiple_game_plies_and_producers_count_as_one_context():
    db = setup_db()
    first = add_game(db, 1, 1)
    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 AND ply=3"
    ).fetchone()[0]
    facts = record_fact_run(
        db,
        position_id=position,
        producer="second",
        detector_version="v1",
        input_data={},
        facts=[{"fact_type": "fork", "payload": {}}],
    )
    with mapping_transaction(db):
        mapped = record_mapping_run_in_transaction(
            db,
            position_id=position,
            producer="second",
            mapper_version="v1",
            subject="learner",
            operation="execute",
            scope_key="fixture",
            input_data={},
            mappings=[
                {
                    "skill": "fork",
                    "outcome": "failure",
                    "confidence": 1,
                    "fact_ids": facts["fact_ids"],
                    "context": {},
                    "observation_at": (NOW - timedelta(days=1)).isoformat(),
                }
            ],
        )
    second = mapped["evidence_ids"][0]
    review_evidence(db, second, decision="accept", actor="fixture-reviewer")
    add_game(db, 2, 2)
    add_game(db, 3, 3)
    result = update_mastery(db, subject="learner", skill="fork", operation="execute", as_of=NOW)
    assert result["context_count"] == 3
    assert result["exclusions"] == {"duplicate_context": 1}
    assert first not in result["supporting_evidence_ids"]
    assert second in result["supporting_evidence_ids"]
    assert result["contexts"][0]["context"]["ply"] == 3


def test_superseded_detector_removes_contribution_without_erasing_history():
    db = setup_db()
    ids = [add_game(db, i, i) for i in range(3)]
    initial = update_mastery(db, subject="learner", skill="fork", operation="execute", as_of=NOW)
    assert initial["status"] == "sufficient"
    position = db.connection.execute(
        "SELECT position_id FROM evidence_mappings WHERE id = ?", (ids[0],)
    ).fetchone()[0]
    record_fact_run(
        db,
        position_id=position,
        producer="detector",
        detector_version="v2",
        input_data={},
        facts=[],
    )
    result = mastery_report(db, subject="learner", as_of=NOW)[0]
    assert result["status"] == "insufficient" and result["context_count"] == 2
    assert db.connection.execute("SELECT is_stale FROM mastery_states").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == 1
