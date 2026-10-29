"""Development cases for checking replies in owned-deep capture observations."""

from pathlib import Path

import chess
import chess.pgn
import httpx
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.material_opportunities import inspect_material_opportunity
from chess_coach.pipeline import process_pipeline
from chess_coach.pipeline_config import PipelineConfig


@pytest.mark.skipif(not Path("/usr/games/stockfish").is_file(), reason="Stockfish not installed")
@pytest.mark.parametrize("black", [False, True])
def test_owned_deep_missed_capture_with_checking_played_reply(tmp_path, black, monkeypatch, capsys):
    board = chess.Board("4k3/7p/8/8/3q4/8/P7/3RK3 w - - 0 1")
    if black:
        board = board.mirror()
    move = "e8f8" if black else "e1f1"
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "fixture_opponent" if black else "fixture_learner"
    game.headers["Black"] = "fixture_learner" if black else "fixture_opponent"
    game.headers["Result"] = "*"
    game.headers["UTCDate"] = "2026.01.01"
    game.headers["UTCTime"] = "12:00:00"
    node = game.add_variation(board.parse_uci(move))
    board.push_uci(move)
    node.add_variation(next(iter(board.legal_moves)))
    db = Database(tmp_path / "deep.sqlite")
    db.initialize()
    ingest_pgn(db, str(game))
    config = PipelineConfig(
        learner="fixture_learner",
        engine_path="/usr/games/stockfish",
        nodes=10000,
        seconds_per_position=1.0,
        deep_per_game=1,
        deep_max_jobs=1,
        deep_max_games=1,
        material_max_decisions=1,
    )
    report = process_pipeline(
        db, config, transport=httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    )
    assert report["deep"]["processed"] == 1
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=?", ("hanging_piece",)
    ).fetchone()
    evidence = inspect_evidence(db, row["id"])
    fact = evidence["context"]["material_observation"]
    assert fact["kind"] == "material_capture" and fact["outcome"] == "failure"
    assert fact["exchange_gain"] == 9 and fact["best"]["uci"][0] == ("d8d5" if black else "d1d4")
    assert any("+" in move for move in fact["played"]["san"])
    assert evidence["context"]["provenance"]["kind"] == "deep"
    view = inspect_material_opportunity(db, row["id"], learner="fixture_learner")
    assert view["lineage"]["detector_version"] == "1.1.0"
    assert view["currentness"] == "current" and view["objective_witness"]
    assert not view["family_validated"] and not view["eligible_for_exercise_candidate"]

    from chess_coach.cli import main
    from chess_coach.web import create_app

    monkeypatch.setattr(
        "sys.argv",
        ["chess-coach", "--db", str(tmp_path / "deep.sqlite"), "inspect-evidence", str(row["id"])],
    )
    main()
    assert "material_capture" in capsys.readouterr().out
    app = create_app(
        db_path=tmp_path / "deep.sqlite",
        subject="fixture_learner",
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        f"/evidence/{row['id']}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert page.status_code == 200
    assert b"tested best continuation captures material" in page.data
    assert b"Material source: current" in page.data and b"captures remain provisional" in page.data
