"""Recurring pawn structures remain descriptive and current-source linked."""

import sys

import chess
import chess.engine
import chess.pgn

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.lesson_narrative import build
from chess_coach.pawn_structure_publish import publish
from chess_coach.pawn_structure_source import prepare_lesson
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.recurrence_report import report
from tests.test_pawn_structure_lessons import FEN, Engine


def _game(day):
    board = chess.Board(FEN)
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": "fixture_learner",
            "Black": "fixture_opponent",
            "UTCDate": f"2026.01.{day:02}",
            "UTCTime": "12:00:00",
            "Result": "*",
        }
    )
    game.add_variation(board.parse_uci("b1c3"))
    return str(game)


def test_independent_current_structures_and_stale_sources(tmp_path, monkeypatch):
    db = Database(tmp_path / "synthetic.sqlite")
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner="fixture_learner", engine_path=sys.executable, nodes=100)
    for day in (1, 2, 3):
        ingest_pgn(db, _game(day))
        game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
        run_analysis(db, game_id, game_input(db, game_id), config, engine_identity(sys.executable))
        position_id = db.connection.execute(
            "SELECT id FROM positions WHERE game_id=?", (game_id,)
        ).fetchone()[0]
        prepared, fact = prepare_lesson(db, position_id, "fixture_learner")
        publish(db, prepared, fact)
    args = (
        db,
        "fixture_learner",
        "2026-01-01T00:00:00+00:00",
        "2026-02-01T00:00:00+00:00",
        "2025-12-01T00:00:00+00:00",
    )
    result = report(*args, skill="pawn_structure", operation="evaluate")
    group = result["current"][0]
    assert group["independent_games"] == group["ambiguous"] == 3
    assert group["misses"] == group["successes"] == 0
    assert group["currentness"] == {"current": 3}
    lesson = build(db, "fixture_learner", group)
    assert len(lesson["examples"]) == 3
    assert all(item["review"] == "unreviewed" for item in lesson["examples"])
    assert all(
        any("isolated pawn on d4" in fact for fact in item["facts"]) for item in lesson["examples"]
    )
    assert all(
        any(line["moves"] == ["Nc3", "Rxd4"] for line in item["lines"])
        for item in lesson["examples"]
    )
    assert any("bounded target-square exchange" in fact for fact in lesson["examples"][0]["facts"])
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0
    from chess_coach.web import create_app

    app = create_app(
        db_path=tmp_path / "synthetic.sqlite",
        subject="fixture_learner",
        actor="fixture",
        corpus="test",
        login="login",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        "/recurrence",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "login"},
        query_string={
            "start": args[2],
            "end": args[3],
            "compare_start": args[4],
            "skill": "pawn_structure",
            "operation": "evaluate",
        },
    )
    assert page.status_code == 200
    assert b"not repeated mistakes" in page.data and b"isolated pawn on d4" in page.data
    assert page.data.count(b"/evidence/") >= 3
    other = report(db, "other", *args[2:], skill="pawn_structure", operation="evaluate")
    assert other["current"] == []
    db.connection.execute(
        "UPDATE mapping_runs SET mapper_version='1.0.0' WHERE position_id=? AND producer='pawn-structure-lesson-mapper'",
        (position_id,),
    )
    db.connection.commit()
    assert (
        report(*args, skill="pawn_structure", operation="evaluate")["current"][0][
            "independent_games"
        ]
        == 2
    )
    db.connection.execute(
        "UPDATE mapping_runs SET mapper_version='1.1.0' WHERE position_id=? AND producer='pawn-structure-lesson-mapper'",
        (position_id,),
    )
    db.connection.execute(
        "UPDATE detector_runs SET detector_version='1.0.0' WHERE position_id=? AND producer='pawn-structure-lesson'",
        (position_id,),
    )
    db.connection.commit()
    assert (
        report(*args, skill="pawn_structure", operation="evaluate")["current"][0][
            "independent_games"
        ]
        == 2
    )
    db.connection.execute(
        "UPDATE detector_runs SET detector_version='1.1.0' WHERE position_id=? AND producer='pawn-structure-lesson'",
        (position_id,),
    )
    db.connection.commit()
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=? AND role='best'",
        (position_id,),
    )
    db.connection.commit()
    result = report(*args, skill="pawn_structure", operation="evaluate")
    assert result["current"][0]["independent_games"] == 2
    assert result["coverage"]["excluded"]["stale"] == 1
    db.connection.execute(
        "UPDATE mapping_runs SET scope_key='wrong' WHERE position_id=? AND producer='pawn-structure-lesson-mapper'",
        (position_id - 1,),
    )
    db.connection.commit()
    result = report(*args, skill="pawn_structure", operation="evaluate")
    assert result["current"][0]["independent_games"] == 1
    assert result["coverage"]["excluded"]["ownership, mapping or review"] == 1
    monkeypatch.setattr(
        "chess_coach.recurrence_candidates.structure_state", lambda *_: "unavailable"
    )
    result = report(*args, skill="pawn_structure", operation="evaluate")
    assert result["current"] == []
    assert result["coverage"]["excluded"]["currentness unavailable"] >= 1


def test_supported_piece_activity_is_descriptive_and_source_linked():
    from chess_coach.lesson_structure import structure
    from chess_coach.pawn_structure_lesson import lesson
    from tests.test_pawn_structure_lessons import line

    board = chess.Board("4r2k/8/8/4N3/3P4/8/8/7K w - - 0 1")
    fact = lesson(board, "d4d5", line("h1g1 e8e5"), line("d4d5 e8e5"))
    facts, lines = structure({"facts": [{"payload": fact}]}, board.fen())
    assert any("pawn on d4 geometrically supports its knight on e5" in item for item in facts)
    assert any(item and item["moves"] == ["d5", "Rxe5"] for item in lines)
    assert fact["mastery_eligible"] is False
