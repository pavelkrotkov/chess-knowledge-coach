"""Descriptive-family probes reuse owned history in the actual report request."""

import sys
from collections import Counter

import chess.engine

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.pawn_structure_publish import publish
from chess_coach.pawn_structure_source import prepare_lesson
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.web import create_app
from tests.test_pawn_structure_lessons import Engine
from tests.test_recurrence_structure_lesson import _game


def test_pawn_structure_probe_and_lesson_share_snapshot_history(tmp_path, monkeypatch):
    import chess_coach.decision_history as decision_history
    import chess_coach.learner_context as learner_context

    path = tmp_path / "structure.sqlite"
    db = Database(path)
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    learner = "fixture_learner"
    config = PipelineConfig(learner=learner, engine_path=sys.executable, nodes=100)
    for day in (1, 2, 3):
        ingest_pgn(db, _game(day))
        game = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
        run_analysis(db, game, game_input(db, game), config, engine_identity(sys.executable))
        position = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=?", (game,)
        ).fetchone()[0]
        prepared, fact = prepare_lesson(db, position, learner)
        publish(db, prepared, fact)
    db.close()
    calls, origins = Counter(), Counter()
    for module in (decision_history, learner_context):
        original = module.decisions

        def counted(connection, game, *, _original=original):
            calls[game["id"]] += 1
            frame = sys._getframe(1)
            while frame is not None:
                name = frame.f_code.co_filename.rsplit("/", 1)[-1]
                if name in {
                    "recurrence_sources.py",
                    "pawn_structure_probe.py",
                    "material_source.py",
                    "decision_inspection.py",
                    "preview_history.py",
                }:
                    origins[name + ":" + frame.f_code.co_name] += 1
                    break
                frame = frame.f_back
            return _original(connection, game)

        monkeypatch.setattr(module, "decisions", counted)
    app = create_app(
        db_path=path,
        subject=learner,
        actor="fixture",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    response = app.test_client().get(
        "/recurrence",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "login"},
        query_string={
            "start": "2026-01-01T00:00:00+00:00",
            "end": "2026-02-01T00:00:00+00:00",
            "compare_start": "2025-12-01T00:00:00+00:00",
            "skill": "pawn_structure",
            "operation": "evaluate",
        },
    )
    assert response.status_code == 200 and b"isolated pawn on d4" in response.data
    assert b"3 recorded candidate positions across 3 independent games" in response.data
    assert len(calls) == 3 and max(calls.values()) <= 2, dict(origins)
