"""Qualified own fork sources remain bound to their real mapping and review."""

import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.fork_detector import process_decision
from chess_coach.related_fork_source import source_for_evidence
from tests.test_fork_pipeline import LEARNER, make_game


def test_qualified_source_and_review_gate(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "fork.sqlite", monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    result = source_for_evidence(db, LEARNER, evidence)
    assert result["outcome"] == "failure" and result["provenance"]["review_status"] == "unreviewed"
    assert result["lines"][0].split()[0] == "b5c7"
    with pytest.raises(ValueError):
        source_for_evidence(db, "fixture_other", evidence)
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        source_for_evidence(db, LEARNER, evidence)


@pytest.mark.parametrize(
    "field,value",
    [
        ("mapper_version", "0.0.0"),
        ("scope_key", "other"),
        ("operation", "prevent"),
        ("subject", "fixture_other"),
        ("status", "superseded"),
    ],
)
def test_run_identity_changes_invalidate_the_exact_source(tmp_path, monkeypatch, field, value):
    db, _ = make_game(tmp_path / "changed.sqlite", monkeypatch)
    result = process_decision(db, 1, LEARNER)
    evidence = result["evidence_ids"][0]
    assert source_for_evidence(db, LEARNER, evidence)
    db.connection.execute(
        f"UPDATE mapping_runs SET {field}=? WHERE id=?", (value, result["mapping_run_id"])
    )
    db.connection.commit()
    with pytest.raises(ValueError):
        source_for_evidence(db, LEARNER, evidence)


def test_changed_analysis_invalidates_the_recorded_source(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "stale.sqlite", monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role='best'"
    )
    db.connection.commit()
    with pytest.raises(ValueError):
        source_for_evidence(db, LEARNER, evidence)


@pytest.mark.parametrize(
    "field,value",
    [
        ("mapper_version", "0.0.0"),
        ("operation", "prevent"),
        ("skill", "hanging_piece"),
        ("subject", "fixture_other"),
    ],
)
def test_mapping_identity_changes_invalidate_source(tmp_path, monkeypatch, field, value):
    db, _ = make_game(tmp_path / "changed-mapping.sqlite", monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    db.connection.execute(f"UPDATE evidence_mappings SET {field}=? WHERE id=?", (value, evidence))
    db.connection.commit()
    with pytest.raises(ValueError):
        source_for_evidence(db, LEARNER, evidence)


def test_missing_active_fact_link_fails_closed(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "unlinked.sqlite", monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    db.connection.execute(
        "UPDATE evidence_fact_links SET active=0 WHERE evidence_id=?", (evidence,)
    )
    db.connection.commit()
    with pytest.raises(ValueError):
        source_for_evidence(db, LEARNER, evidence)
