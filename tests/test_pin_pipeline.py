"""Pin observations retain their current source and stay outside mastery."""

import sys
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.mastery_eligibility import eligible_contexts
from chess_coach.pin_pipeline import process_decision
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.web import create_app


class Engine:
    def __init__(self):
        self.id = {"name": "synthetic"}
        self.options = {}

    def configure(self, settings):
        pass

    def analyse(self, board, limit, multipv, root_moves=None):
        moves = [root_moves[0] if root_moves else next(iter(board.legal_moves))]
        return [
            {
                "score": chess.engine.PovScore(chess.engine.Cp(0), board.turn),
                "pv": moves,
                "nodes": 100,
                "depth": 5,
            }
        ]

    def quit(self):
        pass


def test_source_review_and_closed_mastery(tmp_path, monkeypatch):
    board = chess.Board("2k5/3r1N2/N1n1B2p/3P4/1R6/8/8/1R1K4 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": "fixture_learner",
            "Black": "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:00:00",
        }
    )
    node = game.add_variation(board.parse_uci("b4c4"))
    board.push_uci("b4c4")
    node.add_variation(board.parse_uci("h6h5"))
    path = tmp_path / "pin.sqlite"
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner="fixture_learner", engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    result = process_decision(db, 1, "fixture_learner", "execute")
    assert result["outcome"] == "success"
    evidence_id = result["evidence_ids"][0]
    detail = inspect_evidence(db, evidence_id)
    assert detail["pin_source_currentness"] == "current"
    assert detail["pin_explanation"]["proof"]["san"] == "Rc4"
    assert process_decision(db, 1, "fixture_learner", "execute")["replayed"]
    db.connection.execute(
        "UPDATE mapping_runs SET mapper_version=? WHERE id=?", ("spoof", result["mapping_run_id"])
    )
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["pin_source_currentness"] == "stale"
    db.connection.execute(
        "UPDATE mapping_runs SET mapper_version=? WHERE id=?", ("1.0.1", result["mapping_run_id"])
    )
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["pin_source_currentness"] == "current"
    review_evidence(db, evidence_id, decision="accept", actor="fixture_reviewer")
    eligible, excluded = eligible_contexts(
        db, "fixture_learner", "absolute_pin", "execute", datetime.now(UTC)
    )
    assert not eligible and excluded["pin_family_unvalidated"] == 1
    app = create_app(
        db_path=path,
        subject="fixture_learner",
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        f"/evidence/{evidence_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert page.status_code == 200 and b"Pin source: current" in page.data and b"Rc4" in page.data
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1"
    )
    db.connection.commit()
    assert inspect_evidence(db, evidence_id)["pin_source_currentness"] == "stale"


def test_bounded_worker_publishes_relative_prevention_and_browser_explanation(
    tmp_path, monkeypatch
):
    from chess_coach.pin_worker import process_pins

    board = chess.Board("7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update(
        {
            "White": "fixture_learner",
            "Black": "fixture_opponent",
            "Result": "*",
            "UTCDate": "2026.01.01",
            "UTCTime": "12:00:00",
        }
    )
    node = game.add_variation(board.parse_uci("e2f2"))
    board.push_uci("e2f2")
    node.add_variation(board.parse_uci("e3e1"))
    path = tmp_path / "pin-defense.sqlite"
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner="fixture_learner", engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    report = process_pins(db, config, "prevent")
    assert report["outcomes"]["failure"] == 1
    row = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill=? AND operation=?",
        ("relative_pin", "prevent"),
    ).fetchone()
    evidence = inspect_evidence(db, row["id"])
    assert evidence["pin_source_currentness"] == "current"
    assert evidence["pin_explanation"]["proof"]["san"] == "Rxe1"
    review_evidence(db, row["id"], decision="accept", actor="fixture_reviewer")
    eligible, excluded = eligible_contexts(
        db, "fixture_learner", "relative_pin", "prevent", datetime.now(UTC)
    )
    assert not eligible and excluded["pin_family_unvalidated"] == 1
    app = create_app(
        db_path=path,
        subject="fixture_learner",
        actor="fixture_reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    evidence_id = row["id"]
    page = app.test_client().get(
        f"/evidence/{evidence_id}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert page.status_code == 200
    assert b"Pin source: current" in page.data and b"Rxe1" in page.data and b"Rxe3" in page.data
