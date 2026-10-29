"""Recurrence reuses validated game history while preserving source checks."""

import sys
from collections import Counter

import chess.engine

from chess_coach.db import Database
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.web import create_app
from tests.test_pin_lessons import LEARNER, _publish
from tests.test_pin_pipeline import Engine


def test_recurrence_reuses_history_at_actual_request_boundary(tmp_path, monkeypatch):
    import chess_coach.decision_history as decision_history
    import chess_coach.learner_context as learner_context

    path = tmp_path / "recurrence.sqlite"
    db = Database(path)
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=LEARNER, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    fen = "7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1"
    for day in (1, 2, 3):
        _publish(db, config, fen, "e2f2", day, "prevent")
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM lesson_versions").fetchone()[0] == 0
    db.close()
    calls = Counter()
    for module in (decision_history, learner_context):
        original = module.decisions

        def counted(connection, game, *, _original=original):
            calls[game["id"]] += 1
            return _original(connection, game)

        monkeypatch.setattr(module, "decisions", counted)
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    response = app.test_client().get(
        "/recurrence",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
        query_string={
            "start": "2026-01-01T00:00:00+00:00",
            "end": "2026-02-01T00:00:00+00:00",
            "compare_start": "2025-12-01T00:00:00+00:00",
            "skill": "relative_pin",
            "operation": "prevent",
        },
    )
    assert response.status_code == 200 and b"Rxe1" in response.data and b"Rxe3" in response.data
    assert len(calls) == 3 and max(calls.values()) <= 2
    check = Database(path)
    try:
        assert (
            check.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0]
            == 0
        )
        assert check.connection.execute("SELECT COUNT(*) FROM lesson_versions").fetchone()[0] == 0
    finally:
        check.close()
