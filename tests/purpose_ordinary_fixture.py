"""Synthetic ordinary analysis for diagnostic isolation regressions."""

import sys

import chess.engine

from chess_coach.db import Database
from chess_coach.deep_selection import select_deep
from chess_coach.ingest import ingest_pgn
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.purpose_view import show
from tests.purpose_fixtures import request
from tests.test_deep_selection import LEARNER, Engine


def assert_no_ordinary_analysis(db):
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM deep_analysis_current").fetchone()[0] == 0


def run_ordinary_analysis(db, monkeypatch):
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _binary: Engine())
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    return run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))


def setup_unanalysed(path, pgn):
    db = Database(path)
    db.initialize()
    ingest_pgn(db, pgn)
    return db


def assert_after_selection(db, request_id, before):
    select_deep(db, [1], learner=LEARNER, per_game=2, total=2)
    assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_current").fetchone()[0] == 1
    assert show(db, request_id, LEARNER) == before
    assert request(db) == request_id
