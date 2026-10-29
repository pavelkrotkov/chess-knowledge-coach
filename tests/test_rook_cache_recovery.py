"""A damaged rook lesson cache must not be treated as current."""

import sys

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.rook_plan_probe import state
from chess_coach.rook_plan_source import current_lesson
from chess_coach.rook_plan_worker import process_rook_plans
from tests.test_rook_plans import FEN, Engine

LEARNER = "fixture_learner"


@pytest.fixture
def rook_cache(tmp_path, monkeypatch):
    db = Database(tmp_path / "rook-cache.sqlite")
    db.initialize()
    board = chess.Board(FEN)
    game = chess.pgn.Game()
    game.setup(board)
    game.headers.update({"White": LEARNER, "Black": "fixture_opponent", "Result": "*"})
    game.add_variation(board.parse_uci("h1g1"))
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    assert process_rook_plans(db, config)["processed"] == 1
    assert state(db, 1, LEARNER) == "current"
    yield db
    db.close()


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE detector_facts SET payload_json='not-json'",
        "UPDATE detector_facts SET fact_type='different'",
        "UPDATE detector_runs SET output_hash='changed'",
        "UPDATE mapping_runs SET input_hash='changed'",
        "UPDATE mapping_runs SET output_hash='changed'",
        "UPDATE evidence_mappings SET source_facts_json='[]'",
        "UPDATE evidence_mappings SET context_json='not-json'",
        "UPDATE evidence_fact_links SET active=0",
    ],
)
def test_damaged_cache_is_not_current_and_rollback_restores_replay(rook_cache, sql):
    db = rook_cache
    db.connection.execute("SAVEPOINT corrupt")
    db.connection.execute(sql)
    assert state(db, 1, LEARNER) == "needed"
    db.connection.execute("ROLLBACK TO corrupt")
    db.connection.execute("RELEASE corrupt")
    assert state(db, 1, LEARNER) == "current"


def test_current_lesson_does_not_expose_unknown_decision(rook_cache):
    assert current_lesson(rook_cache, 1, LEARNER) is not None
    assert current_lesson(rook_cache, -1, LEARNER) is None
    assert state(rook_cache, -1, LEARNER) == "unavailable"
