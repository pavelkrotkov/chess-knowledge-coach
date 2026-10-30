"""Synthetic purpose diagnostic coverage."""

from chess_coach.purpose_worker import run
from tests.purpose_fixtures import configure, request
from tests.purpose_stale_checks import assert_stale_attempt
from tests.purpose_ui_assertions import assert_stale_browser
from tests.test_deep_selection import LEARNER, setup_game


def test_source_change_during_search_cannot_publish_current_result(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "stale.sqlite", monkeypatch)
    request_id = request(db)

    def change():
        db.connection.execute("UPDATE games SET pgn=pgn || ? WHERE id=1", (" ",))
        db.connection.commit()

    configure(monkeypatch, db, change=change)
    outcome = run(db, request_id, LEARNER)
    assert outcome["status"] == "stale"
    assert_stale_attempt(db, request_id, "stale", "source_changed")
    assert_stale_browser(db.path, request_id, detail=b"source_changed")


def test_stale_source_before_claim_records_attempt_without_search(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "stale-before-claim.sqlite", monkeypatch)
    request_id = request(db)
    db.connection.execute("UPDATE games SET pgn=pgn || ? WHERE id=1", (" ",))
    db.connection.commit()
    engine = configure(monkeypatch, db)
    outcome = run(db, request_id, LEARNER)
    assert outcome["status"] == "stale" and not engine.calls
    attempt = db.connection.execute(
        "SELECT attempt_number,status,detail FROM purpose_analysis_attempts WHERE request_id=?",
        (request_id,),
    ).fetchone()
    assert tuple(attempt) == (1, "stale", "source_changed")
    assert_stale_attempt(db, request_id, "stale", "source_changed")
