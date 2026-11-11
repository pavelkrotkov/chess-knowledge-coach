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
    optional_scans = []
    monkeypatch.setattr(
        "chess_coach.pipeline.after_pipeline", lambda *_: optional_scans.append("mate")
    )
    monkeypatch.setattr(
        "chess_coach.pipeline.capture_after_pipeline", lambda *_: optional_scans.append("capture")
    )
    monkeypatch.setattr(
        "chess_coach.pipeline.opening_after_pipeline", lambda *_: optional_scans.append("opening")
    )
    monkeypatch.setattr(
        "chess_coach.pipeline.fork_after_pipeline", lambda *_: optional_scans.append("fork")
    )
    monkeypatch.setattr(
        "chess_coach.pipeline.fork_miss_after_pipeline",
        lambda *_: optional_scans.append("fork-miss"),
    )
    result = process_pipeline(db, config, transport=network)
    assert optional_scans == ["mate", "capture", "opening", "fork", "fork-miss"]
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


def test_recent_ordinary_budget_archive_and_single_lane_fairness(tmp_path, monkeypatch):
    from chess_coach.ingest import ingest_pgn
    from chess_coach.lichess_state import account_key
    from chess_coach.mapping_transaction import mapping_transaction
    from chess_coach.pipeline_checkpoint import checkpoint
    from chess_coach.pipeline_inputs import analysis_input, engine_identity, game_input
    from chess_coach.pipeline_ordinary import process_ordinary
    from chess_coach.pipeline_pending import pending_games
    from chess_coach.pipeline_work import run_analysis

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: FakeEngine())
    db = Database(tmp_path / "recent.sqlite")
    db.initialize()
    now = int(time.time())
    for index in range(1, 6):
        ingest_pgn(db, game(f"recent{index:02}", now - 50 + index))
    db.connection.execute("UPDATE games SET variant='Chess960' WHERE id=5")
    db.connection.commit()
    config = PipelineConfig(
        learner="learner",
        max_games=2,
        max_scan=10,
        nodes=100,
        seconds_per_position=0.1,
        engine_path=sys.executable,
    )
    engine_hash = engine_identity(config.engine_path)
    key = analysis_input(game_input(db, 4), config, engine_hash)
    with mapping_transaction(db):
        checkpoint(db.connection, 4, "analysis", key, "failed", "analysis_failed")
    assert run_analysis(db, 3, game_input(db, 3), config, engine_hash)["status"] == "complete"
    games, scan, recent = process_ordinary(db, config, engine_hash)
    assert [item["game_id"] for item in games] == [2, 1]
    assert recent["selected"] == recent["analysis_complete"] == 1
    assert recent["failed"] == recent["current"] == recent["invalid"] == 1
    assert recent["examined"] + scan["examined"] <= config.max_scan
    cursor = db.connection.execute(
        "SELECT last_game_id FROM pipeline_cursors WHERE account_key=?",
        (account_key(config.learner),),
    ).fetchone()[0]
    assert cursor == 1
    pending, scanned, _cursor = pending_games(db, config, engine_hash, exclude={2})
    assert [item[0] for item in pending] == [3, 4]
    assert scanned["examined"] == 3
    retry, _scan, recent = process_ordinary(db, config, engine_hash)
    assert [item["game_id"] for item in retry] == [3, 4]
    assert recent["selected"] == 0
    assert retry[1]["stages"][0]["status"] == "complete"
    db.close()

    db = Database(tmp_path / "single.sqlite")
    db.initialize()
    for index in range(1, 5):
        ingest_pgn(db, game(f"single{index:02}", now - 50 + index))
    config = replace(config, max_games=2, max_scan=1)
    archive, scan, recent = process_ordinary(db, config, engine_hash)
    assert [item["game_id"] for item in archive] == [1]
    assert scan["examined"] == 1 and scan["archive_checked"] and recent["examined"] == 0

    import chess_coach.pipeline_ordinary_recent as recent_worker

    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt()

    with monkeypatch.context() as patch:
        patch.setattr(recent_worker, "process_game", interrupt)
        with pytest.raises(KeyboardInterrupt):
            process_ordinary(db, config, engine_hash)
    archive, scan, recent = process_ordinary(db, config, engine_hash)
    assert [item["game_id"] for item in archive] == [2]
    assert recent["examined"] == 0
    config = replace(config, max_games=1, max_scan=10)
    newest, scan, recent = process_ordinary(db, config, engine_hash)
    assert [item["game_id"] for item in newest] == [4]
    assert recent["analysis_complete"] == 1 and scan["examined"] == 0
    assert not scan["archive_checked"] and scan["has_more"]
    cursor = db.connection.execute(
        "SELECT last_game_id FROM pipeline_cursors WHERE account_key=?",
        (account_key(config.learner),),
    ).fetchone()[0]
    assert cursor == 2
    ingest_pgn(db, game("single05", now - 47))
    archive, scan, recent = process_ordinary(db, config, engine_hash)
    assert [item["game_id"] for item in archive] == [3]
    newest, scan, recent = process_ordinary(db, config, engine_hash)
    assert [item["game_id"] for item in newest] == [5]
    assert recent["analysis_complete"] == 1

    import chess_coach.pipeline_ordinary_archive as archive_worker

    ingest_pgn(db, game("single06", now - 48))
    with monkeypatch.context() as patch:
        patch.setattr(archive_worker, "process_game", interrupt)
        with pytest.raises(KeyboardInterrupt):
            process_ordinary(db, config, engine_hash)
    newest, scan, recent = process_ordinary(db, config, engine_hash)
    assert [item["game_id"] for item in newest] == [6]
    assert recent["analysis_complete"] == 1 and not scan["archive_checked"]
    cursor = db.connection.execute(
        "SELECT last_game_id FROM pipeline_cursors WHERE account_key=?",
        (account_key(config.learner),),
    ).fetchone()[0]
    assert cursor == 3
    db.close()

    db = Database(tmp_path / "full-window.sqlite")
    db.initialize()
    for index in range(1, 4):
        ingest_pgn(db, game(f"window{index:02}", now - 50 + index))
    config = replace(config, max_games=2, max_scan=100)
    initial, _, recent = process_ordinary(db, config, engine_hash)
    assert [item["game_id"] for item in initial] == [3, 1]
    assert recent["analysis_complete"] == 1
    ingest_pgn(db, game("window04", now))
    updated, _, recent = process_ordinary(db, config, engine_hash)
    assert [item["game_id"] for item in updated] == [4, 2]
    assert recent["analysis_complete"] == 1
    db.close()

    from chess_coach.fact_fingerprint import canonical
    from chess_coach.pipeline_recent_state import POLICY, valid
    from chess_coach.pipeline_recent_turn import _key

    for scan_limit in (1, 2):
        db = Database(tmp_path / f"rotation-{scan_limit}.sqlite")
        db.initialize()
        for index in range(1, 9):
            ingest_pgn(db, game(f"rotation{index:02}", now - 50 + index))
        config = replace(config, max_games=2, max_scan=scan_limit)
        assert run_analysis(db, 8, game_input(db, 8), config, engine_hash)["status"] == "complete"
        key = analysis_input(game_input(db, 7), config, engine_hash)
        with mapping_transaction(db):
            checkpoint(db.connection, 7, "analysis", key, "failed", "analysis_failed")
        outcomes = []
        for _ in range(6 if scan_limit == 1 else 3):
            games, scan, recent = process_ordinary(db, config, engine_hash)
            assert recent["examined"] + scan["examined"] <= scan_limit
            outcomes.extend(
                item["game_id"] for item in games if recent["selected"] and item is games[0]
            )
        assert outcomes == [6]

        invalid = {"version": POLICY, "after": ["2026-01-01T00:00:00+00:00", 2**63], "seen": 1}
        assert not valid(invalid)
        assert not valid({"version": POLICY, "after": None, "seen": 1})
        assert not valid({"version": POLICY, "after": [[], 1], "seen": 1})
        db.connection.execute(
            "UPDATE pipeline_cursors SET scan_hash=? WHERE account_key=?",
            (canonical(invalid), _key(config.learner)),
        )
        db.connection.commit()
        process_ordinary(db, config, engine_hash)
        db.close()
