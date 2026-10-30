"""Original setup rights and incomplete history for owned fork defense."""

import sys

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.fork_defense_detector import process_decision
from chess_coach.ingest import ingest_pgn
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from tests.test_fork_defense_pipeline import LEARNER, Engine
from tests.test_objective_fork_defense import begin


def setup_source(path, monkeypatch, fen):
    board = chess.Board(fen)
    moves = ["a1b1", "h8g8", "e1f1", "g7g6"]
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = LEARNER
    game.headers["Black"] = "fixture_opponent"
    game.headers["Result"] = "*"
    game.headers["UTCDate"] = "2026.01.01"
    game.headers["UTCTime"] = "12:00:00"
    node = game.add_variation(board.parse_uci(moves[0]))
    board.push_uci(moves[0])
    node.add_variation(board.parse_uci(moves[1]))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine(moves, moves))
    config = PipelineConfig(
        learner=LEARNER, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    return db, process_decision(db, 1, LEARNER)["evidence_ids"][0]


def test_original_castling_rights_are_retained(tmp_path, monkeypatch):
    db, evidence = setup_source(
        tmp_path / "rights.sqlite", monkeypatch, "7k/6p1/8/8/1n6/8/7P/R3K3 w Q - 0 1"
    )
    state = begin(db, evidence)
    assert state["fen"].split()[2] == "Q"
    db.close()


def test_unknown_pre_setup_history_is_not_silently_assumed(tmp_path, monkeypatch):
    db, evidence = setup_source(
        tmp_path / "unknown.sqlite", monkeypatch, "7k/6p1/8/8/1n6/8/7P/R3K3 w - - 8 10"
    )
    with pytest.raises(ValueError, match="history"):
        begin(db, evidence)
    db.close()
