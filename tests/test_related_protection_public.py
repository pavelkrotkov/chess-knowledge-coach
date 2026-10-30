"""Public transfer lines are filtered and remain source-bound."""

import json

import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.related_protection import preview
from chess_coach.related_protection_start import start_related
from chess_coach.unified_session_events import show, submit
from tests.related_protection_support import add_public, source_and_corpus
from tests.test_material_pipeline import LEARNER


def test_only_matching_public_lines_are_playable_and_other_moves_ungraded(tmp_path, monkeypatch):
    db, evidence = source_and_corpus(tmp_path / "public.sqlite", monkeypatch)
    add_public(db)
    result = preview(db, LEARNER, evidence, "test")
    item = next(item for item in result["items"] if item["type"] == "public")
    state = start_related(
        db,
        attempt_id="public",
        subject=LEARNER,
        evidence_id=evidence,
        corpus_version="test",
        reference=item["reference"],
    )
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
