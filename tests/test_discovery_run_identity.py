"""A discovery source is current only while its linked run identity matches."""

import pytest

from chess_coach.discovery_pipeline import process_discoveries
from chess_coach.discovery_practice import VERSION
from chess_coach.discovery_practice_source import resolve
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.lesson_source import source
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from tests.test_discovery_pipeline import LEARNER, make_game


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("producer", "fixture-foreign"),
        ("mapper_version", "fixture-stale"),
        ("subject", "fixture-foreign"),
        ("operation", "prevent"),
        ("position_id", 2),
        ("scope_key", "fixture-foreign"),
        ("status", "superseded"),
    ],
)
def test_linked_run_identity_invalidates_reviewed_practice_and_lesson(
    tmp_path, monkeypatch, field, replacement
):
    db, config = make_game(tmp_path / "identity.sqlite", monkeypatch)
    process_discoveries(db, config)
    evidence_id = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=?", ("discovered_attack",)
    ).fetchone()[0]
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    start(
        db,
        attempt_id="fixture-attempt",
        subject=LEARNER,
        source_type="own-game",
        version=VERSION,
        key=str(evidence_id),
    )
    evidence = inspect_evidence(db, evidence_id)
    assert evidence["discovery_currentness"] == "current"
    run_id = evidence["mapping_run_id"]
    original = db.connection.execute("SELECT * FROM mapping_runs WHERE id=?", (run_id,)).fetchone()[
        field
    ]
    before = tuple(
        db.connection.execute(
            "SELECT (SELECT COUNT(*) FROM evidence_mappings),(SELECT COUNT(*) FROM evidence_review_events),(SELECT COUNT(*) FROM training_attempts)"
        ).fetchone()
    )
    db.connection.execute(f"UPDATE mapping_runs SET {field}=? WHERE id=?", (replacement, run_id))
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["discovery_currentness"] == "stale"
    assert source(db, LEARNER, {"id": evidence_id, "position_id": evidence["position_id"]}) is None
    with pytest.raises(ValueError):
        resolve(db, VERSION, str(evidence_id), LEARNER)
    with pytest.raises(ValueError):
        show(db, "fixture-attempt", LEARNER)
    with pytest.raises(ValueError):
        submit(db, "fixture-attempt", LEARNER, event_id="fixture-event", move="h6f7")
    assert (
        tuple(
            db.connection.execute(
                "SELECT (SELECT COUNT(*) FROM evidence_mappings),(SELECT COUNT(*) FROM evidence_review_events),(SELECT COUNT(*) FROM training_attempts)"
            ).fetchone()
        )
        == before
    )
    db.connection.execute(f"UPDATE mapping_runs SET {field}=? WHERE id=?", (original, run_id))
    db.connection.commit()
    restored = inspect_evidence(db, evidence_id)
    assert (
        restored["discovery_currentness"] == "current" and restored["review_status"] == "accepted"
    )
    assert resolve(db, VERSION, str(evidence_id), LEARNER)


def test_run_identity_is_rechecked_after_source_verification(tmp_path, monkeypatch):
    from chess_coach import discovery_evidence

    db, config = make_game(tmp_path / "race.sqlite", monkeypatch)
    process_discoveries(db, config)
    evidence_id = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=?", ("discovered_attack",)
    ).fetchone()[0]
    original = discovery_evidence.verified_fen

    def change_during_verification(db, evidence, fact, **kwargs):
        fen = original(db, evidence, fact, **kwargs)
        db.connection.execute(
            "UPDATE mapping_runs SET mapper_version=? WHERE id=?",
            ("fixture-stale", evidence["mapping_run_id"]),
        )
        return fen

    monkeypatch.setattr(discovery_evidence, "verified_fen", change_during_verification)
    assert inspect_evidence(db, evidence_id)["discovery_currentness"] == "stale"
    db.connection.rollback()
