"""Regressions for surviving sources and eligible mastery invalidation."""

import json

from chess_coach.db import Database
from chess_coach.evidence import record_evidence, validate_evidence
from chess_coach.fact_runs import record_fact_run
from chess_coach.mapping_runs import record_mapping_run_in_transaction
from chess_coach.mapping_transaction import mapping_transaction
from chess_coach.mastery import mastery_report, update_mastery
from chess_coach.ontology import map_detector_facts


def setup_db():
    db = Database(":memory:")
    db.initialize()
    db.connection.execute("INSERT INTO games(pgn,white,black,result) VALUES('raw','A','B','*')")
    db.connection.execute("INSERT INTO positions(game_id,ply,fen,san,uci) VALUES(1,1,'fen','','')")
    db.connection.commit()
    return db


def facts(db, producer, version, items):
    return record_fact_run(
        db, position_id=1, producer=producer, detector_version=version, input_data={}, facts=items
    )


def fork():
    return {"fact_type": "fork", "payload": {"motif": "fork"}}


def test_surviving_producer_mapping_and_review_remain_current():
    db = setup_db()
    source_a = facts(db, "a", "v1", [fork()])
    map_detector_facts(db, "v1")
    a_id = db.connection.execute("SELECT id FROM evidence_mappings").fetchone()[0]
    validate_evidence(db, a_id, actor="fixture-reviewer")
    update_mastery(db, subject="unassigned", skill="fork", operation="execute")
    source_b = facts(db, "b", "v1", [fork()])
    assert len(map_detector_facts(db, "v1")) == 2
    assert mastery_report(db, subject="unassigned")
    facts(db, "b", "v2", [])
    assert len(map_detector_facts(db, "v1")) == 1
    assert len(map_detector_facts(db, "v1")) == 1
    active = db.connection.execute(
        """SELECT e.id, e.human_validated, l.fact_id FROM evidence_mappings e
        JOIN mapping_runs r ON r.id=e.mapping_run_id
        JOIN evidence_fact_links l ON l.evidence_id=e.id
        WHERE r.status='active' AND l.active=1"""
    ).fetchall()
    assert [tuple(row) for row in active] == [(a_id, 1, source_a["fact_ids"][0])]
    assert source_b["fact_ids"][0] != source_a["fact_ids"][0]
    assert mastery_report(db, subject="unassigned")
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == 0


def test_legacy_combined_scope_moves_to_independent_fact_scopes_without_review_transfer():
    db = setup_db()
    a = facts(db, "a", "v1", [fork()])
    b = facts(db, "b", "v1", [fork()])
    old_scope = json.dumps({"detector_version": None}, sort_keys=True)
    mappings = [
        {
            "skill": "fork",
            "outcome": "success",
            "confidence": 1.0,
            "fact_ids": [fact_id],
            "context": {},
            "observation_at": None,
        }
        for fact_id in a["fact_ids"] + b["fact_ids"]
    ]
    with mapping_transaction(db):
        old = record_mapping_run_in_transaction(
            db,
            position_id=1,
            producer="ontology",
            mapper_version="v1",
            subject="unassigned",
            operation="execute",
            scope_key=old_scope,
            input_data={"source_fact_ids": a["fact_ids"] + b["fact_ids"]},
            mappings=mappings,
        )
    validate_evidence(db, old["evidence_ids"][0], actor="fixture-reviewer")
    map_detector_facts(db, "v1")
    row = db.connection.execute(
        "SELECT status FROM mapping_runs WHERE id=?", (old["run_id"],)
    ).fetchone()
    assert row[0] == "superseded"
    assert (
        db.connection.execute(
            "SELECT human_validated FROM evidence_mappings WHERE id=?", (old["evidence_ids"][0],)
        ).fetchone()[0]
        == 1
    )
    assert (
        db.connection.execute("""SELECT COUNT(*) FROM evidence_mappings e JOIN mapping_runs r
        ON e.mapping_run_id=r.id WHERE r.status='active' AND e.human_validated=1""").fetchone()[0]
        == 0
    )
    assert len(map_detector_facts(db, "v1")) == 2


def test_unreviewed_manual_or_mapped_evidence_does_not_hide_mastery():
    db = setup_db()
    evidence = record_evidence(
        db, skill="fork", operation="execute", outcome="success", confidence=1, subject="unassigned"
    )
    validate_evidence(db, evidence, actor="fixture-reviewer")
    update_mastery(db, subject="unassigned", skill="fork", operation="execute")
    assert mastery_report(db, subject="unassigned")
    record_evidence(
        db, skill="fork", operation="execute", outcome="failure", confidence=1, subject="unassigned"
    )
    assert mastery_report(db, subject="unassigned")
    facts(db, "a", "v1", [fork()])
    map_detector_facts(db, "v1")
    assert mastery_report(db, subject="unassigned")
    validate_evidence(db, evidence, actor="fixture-reviewer")
    assert mastery_report(db, subject="unassigned")
    newly_reviewed = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE human_validated=0 ORDER BY id LIMIT 1"
    ).fetchone()[0]
    validate_evidence(db, newly_reviewed, actor="fixture-reviewer")
    assert mastery_report(db, subject="unassigned")[0]["status"] == "insufficient"


def test_validating_superseded_evidence_does_not_stale_active_mastery():
    db = setup_db()
    current = record_evidence(
        db, skill="fork", operation="execute", outcome="success", confidence=1, subject="unassigned"
    )
    validate_evidence(db, current, actor="fixture-reviewer")
    update_mastery(db, subject="unassigned", skill="fork", operation="execute")
    facts(db, "a", "v1", [fork()])
    map_detector_facts(db, "v1")
    old_id = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE mapping_run_id IS NOT NULL"
    ).fetchone()[0]
    facts(db, "a", "v2", [])
    validate_evidence(db, old_id, actor="fixture-reviewer")
    assert mastery_report(db, subject="unassigned")
