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


def test_collision_and_changed_output_roll_back(db):
    source = fact(db)
    fact_id = source["fact_ids"][0]
    first = mapping(db, fact_id)
    with pytest.raises(ValueError, match="already mapped"):
        mapping(db, fact_id, producer="other")
    with pytest.raises(ValueError, match="different output"):
        mapping(db, fact_id, value="failure")
    assert db.connection.execute("SELECT COUNT(*) FROM mapping_runs").fetchone()[0] == 1
    assert (
        db.connection.execute(
            "SELECT status FROM mapping_runs WHERE id = ?", (first["run_id"],)
        ).fetchone()[0]
        == "active"
    )


def test_detector_supersession_invalidates_linked_evidence_and_history(db):
    one = fact(db)
    result = mapping(db, one["fact_ids"][0])
    validate_evidence(db, result["evidence_ids"][0], actor="fixture-reviewer")
    update_mastery(db, subject="learner", skill="fork", operation="execute")
    fact(db, version="two")
    assert evidence_report(db) == []
    assert mastery_report(db, subject="learner")[0]["status"] == "insufficient"
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == 0
    assert db.connection.execute("SELECT human_validated FROM evidence_mappings").fetchone()[0] == 1


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


def test_legacy_fact_link_remains_unknown(db):
    db.connection.execute(
        "INSERT INTO detector_facts(position_id, detector_version, fact_type, payload_json) VALUES (1, 'old', 'fork', '{}')"
    )
    db.connection.commit()
    mapped = mapping(db, 1)
    assert (
        db.connection.execute(
            "SELECT source_provenance FROM evidence_mappings WHERE id = ?",
            (mapped["evidence_ids"][0],),
        ).fetchone()[0]
        == "unknown"
    )


def test_failed_v7_migration_rolls_back_schema(monkeypatch):
    from chess_coach import db_recent
    from chess_coach.db import SCHEMA

    legacy = Database(":memory:")
    legacy.connection.executescript(SCHEMA)
    legacy.connection.execute("PRAGMA user_version = 6")
    legacy.connection.commit()
    before = list(
        legacy.connection.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name")
    )
    original = db_recent.add_evidence_lineage

    def fail(connection):
        original(connection)
        raise RuntimeError("migration failed")

    monkeypatch.setattr(db_recent, "add_evidence_lineage", fail)
    with pytest.raises(RuntimeError, match="migration failed"):
        legacy.initialize()
    assert legacy.connection.execute("PRAGMA user_version").fetchone()[0] == 6
    assert (
        list(legacy.connection.execute("SELECT type, name, sql FROM sqlite_master ORDER BY name"))
        == before
    )


def test_other_producer_and_training_evidence_survive_replacement(db):
    from chess_coach.evidence import record_evidence

    manual_id = record_evidence(
        db, skill="fork", operation="execute", outcome="success", confidence=1, subject="training"
    )
    source = fact(db)
    mapping(db, source["fact_ids"][0])
    empty = mapping(db, None, version="two")
    assert empty["status"] == "active"
    assert (
        db.connection.execute(
            "SELECT subject FROM evidence_mappings WHERE id = ?", (manual_id,)
        ).fetchone()[0]
        == "training"
    )
    assert evidence_report(db)[0]["success"] == 1


def test_ontology_keeps_mappings_for_different_subjects(db):
    from chess_coach.ontology import map_detector_facts

    source = fact(db)
    mapping(db, source["fact_ids"][0], producer="motif")
    # Learner identity differs, so an ontology mapping is independent.
    result = map_detector_facts(db, "map")
    assert len(result) == 1
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM mapping_runs WHERE status = 'active'"
        ).fetchone()[0]
        == 2
    )
    assert map_detector_facts(db, "map") == result


def test_scope_replacement_and_insert_failure_is_atomic(db, monkeypatch):
    from chess_coach import mapping_run_storage

    source = fact(db)
    first = mapping(db, source["fact_ids"][0])
    original = mapping_run_storage.insert_mapping

    def fail_after_insert(*args):
        original(*args)
        raise RuntimeError("injected evidence failure")

    monkeypatch.setattr(mapping_run_storage, "insert_mapping", fail_after_insert)
    with pytest.raises(RuntimeError, match="injected evidence failure"):
        mapping(db, source["fact_ids"][0], version="two")
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 1
    assert (
        db.connection.execute(
            "SELECT status FROM mapping_runs WHERE id = ?", (first["run_id"],)
        ).fetchone()[0]
        == "active"
    )
    assert db.connection.execute("SELECT active FROM evidence_fact_links").fetchone()[0] == 1


def test_ontology_rejects_duplicate_effective_fact_from_other_mapper(db):
    from chess_coach.ontology import map_detector_facts

    source = fact(db)
    with mapping_transaction(db):
        first = record_mapping_run_in_transaction(
            db,
            position_id=1,
            producer="motif",
            mapper_version="one",
            subject="unassigned",
            operation="execute",
            scope_key="test",
            input_data={},
            mappings=[
                {
                    "skill": "fork",
                    "outcome": "success",
                    "confidence": 1,
                    "fact_ids": source["fact_ids"],
                    "context": {},
                    "observation_at": None,
                }
            ],
        )
    with pytest.raises(ValueError, match="already mapped"):
        map_detector_facts(db, "map")
    assert db.connection.execute("SELECT COUNT(*) FROM mapping_runs").fetchone()[0] == 1
    assert (
        db.connection.execute(
            "SELECT status FROM mapping_runs WHERE id = ?", (first["run_id"],)
        ).fetchone()[0]
        == "active"
    )


def test_motif_and_ontology_same_fact_collision_rolls_back(db):
    import chess

    from chess_coach.motifs import record_motif_opportunities
    from chess_coach.ontology import map_detector_facts

    board = chess.Board("4k3/8/8/8/8/2N5/8/4K3 w - - 0 1")
    board.set_piece_at(chess.E4, chess.Piece(chess.KNIGHT, chess.WHITE))
    board.set_piece_at(chess.C5, chess.Piece(chess.ROOK, chess.BLACK))
    board.set_piece_at(chess.F6, chess.Piece(chess.BISHOP, chess.BLACK))
    db.connection.execute("UPDATE positions SET fen = ? WHERE id = 1", (board.fen(),))
    db.connection.commit()
    record_motif_opportunities(db, 1, operation="execute")
    before = db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0]
    with pytest.raises(ValueError, match="already mapped"):
        map_detector_facts(db, "one")
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == before
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM mapping_runs WHERE producer = 'ontology'"
        ).fetchone()[0]
        == 0
    )


def test_nested_batch_does_not_commit_the_callers_transaction(db):
    from chess_coach.motifs import record_motif_opportunities

    db.connection.execute(
        "UPDATE positions SET fen = ? WHERE id = 1", ("4k3/8/8/8/8/8/8/4K3 w - - 0 1",)
    )
    record_motif_opportunities(db, 1)
    assert db.connection.in_transaction
    db.connection.rollback()
    assert db.connection.execute("SELECT COUNT(*) FROM detector_runs").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM mapping_runs").fetchone()[0] == 0


def test_other_producer_scope_is_unchanged_by_mapper_rerun(db):
    source = fact(db)
    first = mapping(db, source["fact_ids"][0])
    with mapping_transaction(db):
        other = record_mapping_run_in_transaction(
            db,
            position_id=1,
            producer="independent",
            mapper_version="one",
            subject="learner",
            operation="recognize",
            scope_key="test",
            input_data={},
            mappings=[
                {
                    "skill": "fork",
                    "outcome": "success",
                    "confidence": 1,
                    "fact_ids": source["fact_ids"],
                    "context": {},
                    "observation_at": None,
                }
            ],
        )
    mapping(db, None, version="two")
    assert (
        db.connection.execute(
            "SELECT status FROM mapping_runs WHERE id = ?", (first["run_id"],)
        ).fetchone()[0]
        == "superseded"
    )
    assert (
        db.connection.execute(
            "SELECT status FROM mapping_runs WHERE id = ?", (other["run_id"],)
        ).fetchone()[0]
        == "active"
    )
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM evidence_mappings WHERE id = ?", (other["evidence_ids"][0],)
        ).fetchone()[0]
        == 1
    )
