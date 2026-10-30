"""Bounded sync, durable processing, interruption and explicit review."""

import json
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime

import chess
import chess.engine
import chess.pgn
import httpx
import pytest

from chess_coach.cli_parser import build_parser
from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.pipeline import process_pipeline
from chess_coach.pipeline_config import PipelineConfig


class FakeEngine:
    def __init__(self):
        self.id = {"name": "Fixture Engine"}
        self.options = {}

    def configure(self, settings):
        self.settings = settings

    def analyse(self, board, limit, multipv, root_moves=None):
        moves = root_moves or list(board.legal_moves)
        for move in moves:
            board.push(move)
            mate = board.is_checkmate()
            board.pop()
            if mate:
                return [{"pv": [move], "nodes": 10, "depth": 1}]
        return [{"pv": moves[:1], "nodes": 10, "depth": 1}]

    def quit(self):
        pass


def game(game_id, timestamp):
    board = chess.Board("6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1")
    board.push_uci("g8h8")
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["Event"] = "Synthetic"
    game.headers["Site"] = f"https://lichess.org/{game_id}"
    game.headers["GameId"] = game_id
    game.headers["White"] = "Learner"
    game.headers["Black"] = "Opponent"
    game.headers["Result"] = "1-0"
    when = datetime.fromtimestamp(timestamp, UTC)
    game.headers["UTCDate"] = when.strftime("%Y.%m.%d")
    game.headers["UTCTime"] = when.strftime("%H:%M:%S")
    game.add_variation(board.parse_uci("c5c8"))
    return str(game)


def transport(entries, calls):
    def handler(request):
        calls.append(request)
        since = int(request.url.params.get("since", "0"))
        until = int(request.url.params.get("until", "9999999999999"))
        limit = int(request.url.params["max"])
        games = [pgn for at, pgn in sorted(entries, reverse=True) if since <= at * 1000 < until]
        return httpx.Response(200, text="\n\n".join(games[:limit]))

    return httpx.MockTransport(handler)


def setup(tmp_path, monkeypatch, count=3):
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    now = int(time.time())
    entries = [(now - i * 10, game(f"fixture{i:02}", now - i * 10)) for i in range(1, count + 1)]
    calls = []
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: FakeEngine())
    config = PipelineConfig(
        learner="learner",
        mate_enabled=False,
        max_games=10,
        page_size=10,
        nodes=100,
        seconds_per_position=0.1,
        engine_path=sys.executable,
    )
    return db, config, transport(entries, calls), calls


def evidence_ids(db, producer):
    return [
        row[0]
        for row in db.connection.execute(
            "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE r.producer=? ORDER BY e.id",
            (producer,),
        )
    ]


def test_end_to_end_replay_review_and_version_changes(tmp_path, monkeypatch):
    db, config, network, calls = setup(tmp_path, monkeypatch)
    args = build_parser().parse_args(["process-pipeline"])
    for worker in ("mate", "material"):
        for limit, expected in (("max_scan", 200), ("max_decisions", 50)):
            name = f"{worker}_{limit}"
            assert getattr(args, name) == getattr(config, name) == expected
    result = process_pipeline(db, config, transport=network)
    assert result["sync"]["games"] == 3 and len(result["games"]) == 3
    assert all(item["status"] == "partial" for item in result["games"])
    assert all(item["stages"][2]["detail"] == "opening_not_configured" for item in result["games"])
    initial = {item["skill"]: item for item in result["mastery"]}
    assert initial["mate_in_one"]["status"] == "insufficient"
    assert "learner" not in json.dumps(result).lower()
    ids = evidence_ids(db, "mate-in-one-mapper")
    fork_ids = evidence_ids(db, "fork-opportunity-mapper")
    assert len(ids) == len(fork_ids) == 3
    assert result["forks"]["outcomes"] == {"ambiguous": 3}
    for evidence in ids:
        review_evidence(db, evidence, decision="accept", actor="fixture-reviewer")
    replay = process_pipeline(db, config, transport=network)
    assert replay["games"] == []
    assert evidence_ids(db, "mate-in-one-mapper") == ids
    assert evidence_ids(db, "fork-opportunity-mapper") == fork_ids
    assert replay["forks"]["replayed"] == 3
    reports = {item["skill"]: item for item in replay["mastery"]}
    assert reports["mate_in_one"]["status"] == "sufficient"
    assert reports["mate_in_one"]["context_count"] == 3
    assert reports["fork"]["status"] == "insufficient"
    assert reports["fork"]["context_count"] == 0
    assert all(
        inspect_evidence(db, evidence)["review_status"] == "unreviewed" for evidence in fork_ids
    )
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 3
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 3
    changed = process_pipeline(db, replace(config, structure_version="v2"), transport=network)
    assert len(changed["games"]) == 3
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 3
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 6
    assert evidence_ids(db, "mate-in-one-mapper") == ids
    assert evidence_ids(db, "fork-opportunity-mapper") == fork_ids
    assert len(calls) <= config.network_requests * 3


def test_analysis_checkpoint_rolls_back_on_interruption(tmp_path, monkeypatch):
    from chess_coach import pipeline_work

    db, config, network, _ = setup(tmp_path, monkeypatch, count=1)
    original = pipeline_work.checkpoint

    def interrupt(*args, **kwargs):
        original(*args, **kwargs)
        raise KeyboardInterrupt()

    with monkeypatch.context() as patch:
        patch.setattr(pipeline_work, "checkpoint", interrupt)
        with pytest.raises(KeyboardInterrupt):
            process_pipeline(db, config, transport=network)
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM pipeline_stages").fetchone()[0] == 0
    assert len(process_pipeline(db, config, transport=network)["games"]) == 1
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 1


@pytest.mark.parametrize("interrupted_stage", ["structures", "opening", "tactical"])
def test_replay_after_stage_commit_before_checkpoint(tmp_path, monkeypatch, interrupted_stage):
    from chess_coach import pipeline_stage

    db, config, network, _ = setup(tmp_path, monkeypatch, count=1)
    from chess_coach.openings import import_openings

    path = tmp_path / "openings.tsv"
    path.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, path, version="fixture", source_url="fixture://opening")
    config = replace(config, opening_version="fixture", opening_source="fixture://opening")
    original = pipeline_stage.checkpoint

    def interrupt(connection, game_id, stage, *args, **kwargs):
        if stage == interrupted_stage:
            raise KeyboardInterrupt()
        return original(connection, game_id, stage, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline_stage, "checkpoint", interrupt)
        with pytest.raises(KeyboardInterrupt):
            process_pipeline(db, config, transport=network)
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 1
    intent = db.connection.execute(
        "SELECT generation,status FROM pipeline_stages WHERE stage=?", (interrupted_stage,)
    ).fetchone()
    assert tuple(intent) == (1, "pending")
    process_pipeline(db, config, transport=network)
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM opening_runs").fetchone()[0] == 1
    assert len(evidence_ids(db, "mate-in-one-mapper")) == 1
    assert len(evidence_ids(db, "fork-opportunity-mapper")) == 1
    assert (
        db.connection.execute(
            "SELECT generation FROM pipeline_stages WHERE stage=?", (interrupted_stage,)
        ).fetchone()[0]
        == 1
    )


def test_stockfish_smoke_with_explicit_resource_limits(tmp_path):
    from pathlib import Path

    from chess_coach.ingest import ingest_pgn

    if not Path("/usr/games/stockfish").is_file():
        pytest.skip("Stockfish is not installed")
    db = Database(tmp_path / "real.sqlite")
    db.initialize()
    ingest_pgn(db, game("smoke001", int(time.time()) - 10))
    config = PipelineConfig(
        learner="learner", nodes=100, seconds_per_position=0.1, threads=1, hash_mb=16
    )
    result = process_pipeline(
        db, config, transport=httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    )
    assert result["games"][0]["stages"][0]["status"] == "complete"
    row = db.connection.execute("SELECT config_json FROM analysis_runs").fetchone()
    recorded = json.loads(row[0])
    assert (
        recorded["nodes"],
        recorded["time_limit"],
        recorded["threads"],
        recorded["hash_mb"],
    ) == (100, 0.1, 1, 16)
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == 1


def test_network_logging_never_exposes_account_or_token(tmp_path, monkeypatch, caplog):
    import logging

    db, config, network, _ = setup(tmp_path, monkeypatch, count=1)
    with caplog.at_level(logging.DEBUG):
        result = process_pipeline(db, config, token="synthetic-secret", transport=network)
    assert result["sync"]["games"] == 1
    assert "synthetic-secret" not in caplog.text
    assert "/games/user/learner" not in caplog.text.lower()
