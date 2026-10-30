"""Synthetic purpose diagnostic coverage."""

from chess_coach.purpose_claim import claim
from chess_coach.purpose_view import show
from chess_coach.purpose_worker import run
from tests.purpose_fixtures import configure, request
from tests.test_deep_selection import LEARNER, setup_game


def test_interrupted_attempt_is_recorded_and_retry_is_bounded(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "retry.sqlite", monkeypatch)
    request_id = request(db)
    claimed, state = claim(db, request_id, LEARNER, retry=False)
    assert claimed and state is None
    assert run(db, request_id, LEARNER)["status"] == "interrupted"
    assert run(db, request_id, LEARNER)["status"] == "retry_required_or_exhausted"
    configure(monkeypatch, db)
    assert run(db, request_id, LEARNER, retry=True)["status"] == "complete"
    assert [item["status"] for item in show(db, request_id, LEARNER)["attempts"]] == [
        "interrupted",
        "complete",
    ]


def test_explicit_retry_cannot_exceed_two_attempts(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "retry-limit.sqlite", monkeypatch)
    request_id = request(db)
    first = configure(monkeypatch, db, mode="timeout")
    assert run(db, request_id, LEARNER)["detail"] == "engine_timeout"
    assert first.closed
    second = configure(monkeypatch, db, mode="timeout")
    assert run(db, request_id, LEARNER, retry=True)["detail"] == "engine_timeout"
    assert second.closed
    third = configure(monkeypatch, db)
    assert run(db, request_id, LEARNER, retry=True)["status"] == "retry_required_or_exhausted"
    assert not third.calls
    assert len(show(db, request_id, LEARNER)["attempts"]) == 2
