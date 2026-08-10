from chess_coach.db import Database
from chess_coach.evidence import evidence_report, record_evidence


def test_evidence_report_keeps_success_failure_and_ambiguity(tmp_path):
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    record_evidence(db, skill="fork", operation="prevent", outcome="success", confidence=0.9)
    record_evidence(db, skill="fork", operation="prevent", outcome="failure", confidence=0.8)
    record_evidence(db, skill="fork", operation="prevent", outcome="ambiguous", confidence=0.3)

    assert evidence_report(db) == [{
        "skill": "fork",
        "operation": "prevent",
        "opportunities": 3,
        "success": 1,
        "failure": 1,
        "ambiguous": 1,
    }]
