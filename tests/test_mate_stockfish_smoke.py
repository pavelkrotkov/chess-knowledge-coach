"""Synthetic production-budget smoke; no real account data or network access."""

import json
from pathlib import Path

import httpx
import pytest

from chess_coach.db import Database
from chess_coach.ingest import ingest_pgn
from chess_coach.pipeline import process_pipeline
from chess_coach.pipeline_config import PipelineConfig


@pytest.mark.skipif(not Path("/usr/games/stockfish").is_file(), reason="Stockfish unavailable")
def test_real_stockfish_pipeline_uses_production_limits(tmp_path):
    db = Database(tmp_path / "synthetic.sqlite")
    db.initialize()
    ingest_pgn(
        db,
        """[Event "Synthetic"]
[White "fixture_a"]
[Black "fixture_b"]
[SetUp "1"]
[FEN "7k/8/5KQ1/8/8/8/8/8 w - - 0 1"]
[UTCDate "2026.01.01"]
[UTCTime "00:00:00"]
[Result "*"]

1. Qg1 *
""",
    )
    config = PipelineConfig(
        learner="fixture_a",
        deep_max_games=1,
        deep_max_jobs=1,
        deep_per_game=1,
        material_enabled=False,
        mate_max_decisions=1,
    )
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    result = process_pipeline(db, config, transport=transport)
    assert result["mate"]["outcomes"] == {"opportunity": 1}
    assert result["deep"]["processed"] == 1
    cheap = json.loads(
        db.connection.execute(
            "SELECT a.config_json FROM analysis_runs a JOIN pipeline_stages s ON s.output_id=a.id WHERE s.game_id=1 AND s.stage='analysis' AND s.status='complete'"
        ).fetchone()[0]
    )
    deep = json.loads(
        db.connection.execute(
            "SELECT config_json FROM deep_analysis_jobs ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    )
    assert (cheap["nodes"], cheap["time_limit"], cheap["hash_mb"]) == (10000, 1.0, 64)
    assert (deep["nodes"], deep["time_limit"], deep["multipv"], deep["hash_mb"]) == (
        50000,
        2.0,
        3,
        64,
    )
