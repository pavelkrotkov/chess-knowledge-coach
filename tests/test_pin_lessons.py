"""Current pin facts feed bounded recurrence and grounded coaching."""

import json
import sys

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.lesson_decision import lessons
from chess_coach.lesson_lines import legal_san
from chess_coach.lesson_narrative import build
from chess_coach.lesson_source import source
from chess_coach.pin_pipeline import process_decision
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.recurrence_report import report
from tests.test_pin_pipeline import Engine

LEARNER = "fixture_learner"


def _game(fen, move, day):
    board = chess.Board(fen)
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": LEARNER,
            "Black": "fixture_opponent",
            "Result": "*",
            "UTCDate": f"2026.01.{day:02}",
            "UTCTime": "12:00:00",
        }
    )
    game.add_variation(board.parse_uci(move))
    return str(game)


def _publish(db, config, fen, move, day, operation):
    ingest_pgn(db, _game(fen, move, day))
    game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
    result = run_analysis(
        db, game_id, game_input(db, game_id), config, engine_identity(sys.executable)
    )
    assert result["status"] == "complete"
    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=? AND ply=1", (game_id,)
    ).fetchone()[0]
    observation = process_decision(db, position, LEARNER, operation)
    assert observation["evidence_ids"]
    return position, observation


@pytest.mark.parametrize(
    ("fen", "move", "operation", "outcome"),
    [
        ("2k5/3r1N2/N1n1B2p/3P4/1R6/8/8/1R1K4 w - - 0 1", "b4c4", "execute", "success"),
        ("4r2k/b1p5/Bpnppppp/8/8/8/8/7K w - - 0 1", "a6b5", "execute", "success"),
        ("4k3/8/B1n5/3P4/8/8/8/4K3 w - - 0 1", "a6b5", "execute", "ambiguous"),
        ("7k/8/8/4r3/8/8/4R3/4K3 w - - 0 1", "e2e3", "prevent", "failure"),
        ("7k/8/8/4r3/8/8/4R3/4K3 w - - 0 1", "e2e5", "prevent", "success"),
        ("7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1", "e2f2", "prevent", "failure"),
        ("7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1", "e2e3", "prevent", "success"),
    ],
)
def test_single_decision_lesson_uses_legal_current_pin_source(
    tmp_path, monkeypatch, fen, move, operation, outcome
):
    db = Database(tmp_path / "pin.sqlite")
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=LEARNER, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    position, item = _publish(db, config, fen, move, 1, operation)
    assert item["outcome"] == outcome
    lesson = lessons(db, LEARNER, position)[0]
    example = lesson["examples"][0]
    assert example["evidence_id"] == item["evidence_ids"][0]
    assert example["facts"] and example["lines"]
    assert all(legal_san(fen, entry["moves"]) == entry["moves"] for entry in example["lines"])
    assert "mastery remains closed" in lesson["qualification"]
    if outcome == "ambiguous":
        assert any("unresolved" in fact for fact in example["facts"])
    elif operation == "execute":
        assert any("legal immediate replies" in fact for fact in example["facts"])
    else:
        assert any("pawn units" in fact or "checkmates" in fact for fact in example["facts"])
    assert lessons(db, "fixture_other", position) == []
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0


def test_recurrence_lessons_recheck_pin_source_and_preserve_review_state(tmp_path, monkeypatch):
    fen = "7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1"
    db = Database(tmp_path / "recurrence.sqlite")
    db.initialize()
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=LEARNER, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    positions = [_publish(db, config, fen, "e2f2", day, "prevent") for day in (1, 2, 3)]
    args = (
        db,
        LEARNER,
        "2026-01-01T00:00:00+00:00",
        "2026-02-01T00:00:00+00:00",
        "2025-12-01T00:00:00+00:00",
    )
    group = report(*args, skill="relative_pin", operation="prevent")["current"][0]
    assert group["independent_games"] == group["misses"] == 3
    lesson = build(db, LEARNER, group)
    assert len(lesson["examples"]) == 3
    assert all(item["review"] == "unreviewed" for item in lesson["examples"])
    assert all(
        any(entry["moves"] == ["Rf2", "Rxe1"] for entry in item["lines"])
        for item in lesson["examples"]
    )
    assert all(
        any(entry["moves"] == ["Rxe3"] for entry in item["lines"]) for item in lesson["examples"]
    )
    from chess_coach.web import create_app

    app = create_app(
        db_path=tmp_path / "recurrence.sqlite",
        subject=LEARNER,
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture-login"}
    page = client.get(
        "/recurrence",
        base_url="https://coach.invalid",
        headers=headers,
        query_string={
            "start": args[2],
            "end": args[3],
            "compare_start": args[4],
            "skill": "relative_pin",
            "operation": "prevent",
        },
    )
    assert page.status_code == 200 and b"Rxe1" in page.data and b"Rxe3" in page.data
    decision_page = client.get(
        f"/decisions/{positions[0][0]}", base_url="https://coach.invalid", headers=headers
    )
    assert decision_page.status_code == 200 and b"Diagnostic question" in decision_page.data
    assert b"Rxe1" in decision_page.data and b"mastery remains closed" in decision_page.data
    first_position, first = positions[0]
    first_id = first["evidence_ids"][0]
    db.connection.execute(
        "UPDATE mapping_runs SET mapper_version=? WHERE id=?", ("1.0.0", first["mapping_run_id"])
    )
    db.connection.commit()
    assert source(db, LEARNER, {"id": first_id, "position_id": first_position}) is None
    assert (
        report(*args, skill="relative_pin", operation="prevent")["current"][0]["independent_games"]
        == 2
    )
    db.connection.execute(
        "UPDATE mapping_runs SET mapper_version=? WHERE id=?", ("1.0.1", first["mapping_run_id"])
    )
    db.connection.execute(
        "UPDATE mapping_runs SET scope_key=? WHERE id=?", ("wrong", first["mapping_run_id"])
    )
    db.connection.commit()
    assert (
        report(*args, skill="relative_pin", operation="prevent")["current"][0]["independent_games"]
        == 2
    )
    db.connection.execute(
        "UPDATE mapping_runs SET scope_key=? WHERE id=?",
        ("pin-prevent-v1", first["mapping_run_id"]),
    )
    db.connection.commit()
    assert (
        report(*args, skill="relative_pin", operation="prevent")["current"][0]["independent_games"]
        == 3
    )
    saved_input = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE id=?", (first["detector_run_id"],)
    ).fetchone()[0]
    source_data = json.loads(saved_input)
    del source_data["detector_input"]["source_marker"]
    db.connection.execute(
        "UPDATE detector_runs SET input_json=? WHERE id=?",
        (json.dumps(source_data), first["detector_run_id"]),
    )
    db.connection.commit()
    missing = report(*args, skill="relative_pin", operation="prevent")
    assert missing["current"][0]["independent_games"] == 2
    assert missing["coverage"]["excluded"]["currentness unavailable"] == 1
    db.connection.execute(
        "UPDATE detector_runs SET input_json=? WHERE id=?", (saved_input, first["detector_run_id"])
    )
    db.connection.commit()
    position, last = positions[-1]
    evidence_id = last["evidence_ids"][0]
    row = db.connection.execute(
        "SELECT context_json FROM evidence_mappings WHERE id=?", (evidence_id,)
    ).fetchone()
    context = json.loads(row[0])
    context["played_move"] = "fabricated"
    db.connection.execute(
        "UPDATE evidence_mappings SET context_json=? WHERE id=?", (json.dumps(context), evidence_id)
    )
    db.connection.commit()
    assert lessons(db, LEARNER, position)[0]["examples"][0]["played"] == "Rf2"
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=?",
        (position,),
    )
    db.connection.commit()
    assert source(db, LEARNER, {"id": evidence_id, "position_id": position}) is None
    current = report(*args, skill="relative_pin", operation="prevent")
    assert current["current"][0]["independent_games"] == 2
    assert current["coverage"]["excluded"]["stale"] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0


def test_ambiguous_competing_mate_keeps_the_counterfactual_pin_line():
    from chess_coach.lesson_pin import pin
    from chess_coach.pin_defense import observe
    from chess_coach.pin_explanation import explain

    board = chess.Board("2k5/3r1N2/N1n1B2p/3P4/1R6/8/8/1R1K4 b - - 0 1")
    actual = board.parse_uci("c6a5")
    fact = observe(board, actual.uci(), None, None)
    assert fact["outcome"] == "ambiguous"
    evidence = {
        "operation": "prevent",
        "lesson_played_san": board.san(actual),
        "pin_explanation": explain(fact, board.fen()),
    }
    facts, lines = pin(evidence, board.fen())
    assert facts and lines and lines[0]["moves"][0] == fact["alternative"]["san"]
    assert legal_san(board.fen(), lines[0]["moves"]) == lines[0]["moves"]
