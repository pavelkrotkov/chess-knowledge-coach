from chess_coach.db import Database
from chess_coach.evidence import record_evidence, validate_evidence
from chess_coach.mastery import mastery_report, update_mastery


def test_mastery_requires_human_validated_evidence_and_preserves_context(tmp_path):
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    record_evidence(
        db,
        skill="fork",
        operation="execute",
        outcome="success",
        confidence=0.9,
        context={
            "rating": 1500,
            "time_control": "blitz",
            "clock": 12,
            "phase": "middlegame",
            "opening_familiarity": 0.4,
        },
    )
    assert update_mastery(db, skill="fork", operation="execute") is None

    evidence_id = db.connection.execute("SELECT id FROM evidence_mappings").fetchone()[0]
    validate_evidence(db, evidence_id)
    state = update_mastery(db, skill="fork", operation="execute")

    assert state is not None
    assert state["mastery"] > 0.5
    assert state["evidence_weight"] == 0.9
    report = mastery_report(db)
    assert report[0]["supporting_evidence_ids"] == [evidence_id]
    assert report[0]["contexts"][0]["context"]["rating"] == 1500
    assert (
        db.connection.execute("SELECT previous_mastery FROM mastery_events").fetchone()[0] is None
    )


def test_mastery_tracks_failure_and_recent_trend(tmp_path):
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    for outcome in ("success", "failure"):
        record_evidence(db, skill="pin", operation="prevent", outcome=outcome, confidence=1.0)
    ids = [row[0] for row in db.connection.execute("SELECT id FROM evidence_mappings")]
    for evidence_id in ids:
        validate_evidence(db, evidence_id)
    state = update_mastery(db, skill="pin", operation="prevent")

    assert state is not None
    assert state["evidence_weight"] == 2.0
    assert state["trend_30d"] == 0.0
    assert mastery_report(db)[0]["state"] in {"developing", "uncertain"}


def test_ambiguous_evidence_does_not_reduce_uncertainty(tmp_path):
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    record_evidence(db, skill="pin", operation="prevent", outcome="ambiguous", confidence=1.0)
    evidence_id = db.connection.execute("SELECT id FROM evidence_mappings").fetchone()[0]
    validate_evidence(db, evidence_id)

    state = update_mastery(db, skill="pin", operation="prevent")

    assert state is not None
    assert state["evidence_weight"] == 0
    assert state["uncertainty"] == 1.0
