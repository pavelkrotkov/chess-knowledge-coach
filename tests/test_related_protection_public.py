"""Public transfer lines are filtered and remain source-bound."""

import json
import sqlite3

import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.related_protection import preview
from chess_coach.related_protection_start import start_related
from chess_coach.unified_session_events import show, submit
from tests.related_protection_support import add_public, source_and_corpus, start_public_session
from tests.test_material_pipeline import LEARNER


def test_only_matching_public_lines_are_playable_and_other_moves_ungraded(tmp_path, monkeypatch):
    db, evidence = source_and_corpus(tmp_path / "public.sqlite", monkeypatch)
    add_public(db)
    _, state = start_public_session(db, evidence, LEARNER, "public")
    assert state["protection_target"] == "d4"
    row = db.connection.execute(
        "SELECT lines_json,provenance_json FROM unified_sessions WHERE attempt_id='public'"
    ).fetchone()
    assert json.loads(row["lines_json"]) == [["d4d3", "e8f8", "d3d2"]]
    binding = json.loads(row["provenance_json"])["related_protection"]
    assert binding["selected_line_indices"] == [1] and binding["operation"] == "prevent"
    event = submit(db, "public", LEARNER, event_id="alternative", move="a2a3")
    assert event["status"] == "needs_verification" and event["feedback"] == "needs_verification"
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0


def test_review_reject_invalidates_preview_and_active_session(tmp_path, monkeypatch):
    db, evidence = source_and_corpus(tmp_path / "stale.sqlite", monkeypatch)
    item = preview(db, LEARNER, evidence, "test")["items"][0]
    start_related(
        db,
        attempt_id="session",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        show(db, "session", LEARNER)
    with pytest.raises(ValueError):
        preview(db, LEARNER, evidence, "test")
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="stale",
            subject=LEARNER,
            evidence_id=evidence,
            corpus_version="test",
            reference=item["reference"],
        )


@pytest.mark.parametrize("change", ["lines", "license"])
def test_public_source_change_invalidates_reference_and_active_session(
    tmp_path, monkeypatch, change
):
    db, evidence = source_and_corpus(tmp_path / "public-change.sqlite", monkeypatch)
    add_public(db)
    item, _ = start_public_session(db, evidence, LEARNER, "public-change")
    if change == "lines":
        statement = "UPDATE public_tasks SET lines_json=? WHERE task_id='fixture'"
        values = (json.dumps(["d4d3 e8f8 d3d2"]),)
        trigger = "immutable_update_public_tasks"
    else:
        statement = "UPDATE public_collections SET license='changed' WHERE version='public-v1'"
        values = ()
        trigger = "immutable_update_public_collections"
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute(statement, values)
    db.connection.rollback()
    # Simulate damaged storage after proving the normal immutability guard works.
    db.connection.execute(f"DROP TRIGGER {trigger}")
    db.connection.execute(statement, values)
    db.connection.commit()
    with pytest.raises(ValueError, match=r"stale|unavailable"):
        show(db, "public-change", LEARNER)
    with pytest.raises(ValueError):
        start_related(
            db,
            attempt_id="public-stale",
            subject=LEARNER,
            evidence_id=evidence,
            corpus_version="test",
            reference=item["reference"],
        )


def test_foreign_subject_cannot_preview_owned_protection(tmp_path, monkeypatch):
    db, evidence = source_and_corpus(tmp_path / "foreign.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        preview(db, "synthetic-foreign-subject", evidence, "test")
