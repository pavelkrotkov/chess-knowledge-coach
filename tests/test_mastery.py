from chess_coach.db import Database
from chess_coach.evidence import record_evidence, validate_evidence
from chess_coach.mastery import mastery_report, update_mastery


def test_unreviewed_and_legacy_sources_never_create_mastery(tmp_path):
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    evidence_id = record_evidence(
        db,
        skill="fork",
        operation="execute",
        outcome="success",
        confidence=0.9,
        subject="learner",
        context={"rating": 1500, "claimed_origin": "another-game"},
    )
    before = update_mastery(db, subject="learner", skill="fork", operation="execute")
    assert before["status"] == "insufficient" and before["mastery"] is None
    assert before["exclusions"] == {"unreviewed_or_invalid_review": 1}
    validate_evidence(db, evidence_id, actor="fixture-reviewer")
    after = mastery_report(db, subject="learner")[0]
    assert after["status"] == "insufficient" and after["mastery"] is None
    assert after["exclusions"] == {"superseded_or_unscoped": 1}
    assert after["contexts"] == []
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
