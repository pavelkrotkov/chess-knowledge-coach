"""Owned fork tasks reject foreign, revoked and changed evidence."""

import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.objective_fork_contract import VERSION
from chess_coach.objective_verify import compute
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from tests.objective_fork_support import SUBJECT, begin, owned_fork


def test_foreign_rejected_and_revoked_sources_cannot_start(tmp_path, monkeypatch):
    db, evidence = owned_fork(tmp_path / "review.sqlite", monkeypatch, "f6g5")
    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="foreign",
            subject="fixture_other",
            source_type="own-game",
            version=VERSION,
            key=str(evidence),
        )
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        begin(db, evidence, "rejected")
    review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
    begin(db, evidence, "accepted")
    review_evidence(db, evidence, decision="revoke", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        show(db, "accepted", SUBJECT)
    with pytest.raises(ValueError):
        begin(db, evidence, "revoked")


def test_source_review_change_before_atomic_publication_is_unresolved(tmp_path, monkeypatch):
    db, evidence = owned_fork(tmp_path / "race.sqlite", monkeypatch, "f6g5")
    begin(db, evidence)
    submit(db, "fork", SUBJECT, event_id="answer", move="b5d6")

    def revoke(database, request, clock, *, seconds):
        result = compute(database, request, clock, seconds=seconds)
        assert result["status"] == "correct"
        review_evidence(database, evidence, decision="reject", actor="fixture_reviewer")
        return result

    assert process(db, SUBJECT, verifier=revoke)["outcomes"] == {"unresolved": 1}
    row = db.connection.execute("SELECT result_json FROM objective_results").fetchone()
    import json

    result = json.loads(row[0])
    assert result["reason"] == "source_unavailable" and result["learning_eligible"] is False


def test_changed_producer_input_invalidates_existing_attempt(tmp_path, monkeypatch):
    db, evidence = owned_fork(tmp_path / "stale.sqlite", monkeypatch, "f6g5")
    begin(db, evidence)
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    with pytest.raises(ValueError):
        show(db, "fork", SUBJECT)
    with pytest.raises(ValueError):
        submit(db, "fork", SUBJECT, event_id="answer", move="b5d6")
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0


@pytest.mark.parametrize("field", ["mapper_version", "scope_key", "operation", "producer"])
def test_changed_mapping_scope_or_identity_is_rejected(tmp_path, monkeypatch, field):
    db, evidence = owned_fork(tmp_path / "mapping.sqlite", monkeypatch, "f6g5")
    run_id = db.connection.execute(
        "SELECT mapping_run_id FROM evidence_mappings WHERE id=?", (evidence,)
    ).fetchone()[0]
    db.connection.execute(
        f"UPDATE mapping_runs SET {field}=? WHERE id=?", ("fixture_changed", run_id)
    )
    db.connection.commit()
    with pytest.raises(ValueError):
        begin(db, evidence)


def test_mismatched_evidence_mapper_version_is_rejected(tmp_path, monkeypatch):
    db, evidence = owned_fork(tmp_path / "evidence-version.sqlite", monkeypatch, "f6g5")
    db.connection.execute(
        "UPDATE evidence_mappings SET mapper_version=? WHERE id=?", ("1.0.0", evidence)
    )
    db.connection.commit()
    with pytest.raises(ValueError):
        begin(db, evidence)
