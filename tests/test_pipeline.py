"""Bounded sync, durable processing, interruption and explicit review."""

import json
import sys
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import chess
import chess.engine
import chess.pgn
import httpx
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import inspect_evidence, review_evidence
from chess_coach.pipeline import process_pipeline
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_lock import pipeline_lock


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


def test_lock_and_retry_after_budget(tmp_path, monkeypatch):
    db, config, _, _ = setup(tmp_path, monkeypatch, count=1)
    with pipeline_lock(db.path), pytest.raises(RuntimeError, match="already running"):
        process_pipeline(
            db, config, transport=httpx.MockTransport(lambda request: httpx.Response(200))
        )
    calls = []

    def rate_limited(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "120"})

    result = process_pipeline(
        db, replace(config, network_sleep=1), transport=httpx.MockTransport(rate_limited)
    )
    assert result["sync"]["status"] == "waiting"
    assert result["sync"]["detail"] == "server_backoff"
    assert result["sync"]["retry_until"]
    assert len(calls) == 1


def test_changed_versions_revert_with_new_truthful_generations(tmp_path, monkeypatch):
    from chess_coach.openings import import_openings

    db, config, network, _ = setup(tmp_path, monkeypatch, count=1)
    openings = tmp_path / "openings.tsv"
    openings.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, openings, version="fixture", source_url="fixture://opening")
    base = replace(
        config,
        opening_version="fixture",
        opening_source="fixture://opening",
        structure_version="v1",
        classifier_version="v1",
        tactical_version="v1",
    )
    changed = replace(base, structure_version="v2", classifier_version="v2", tactical_version="v2")
    for selected in (base, changed, base):
        result = process_pipeline(db, selected, transport=network)
        assert len(result["games"]) == 1
        assert all(stage["status"] == "complete" for stage in result["games"][0]["stages"])
    for table, column in (
        ("structure_runs", "detector_version"),
        ("opening_runs", "classifier_version"),
    ):
        rows = db.connection.execute(
            f"SELECT {column},status,pipeline_generation FROM {table} ORDER BY id"
        ).fetchall()
        assert [tuple(row) for row in rows] == [
            ("v1", "superseded", 1),
            ("v2", "superseded", 2),
            ("v1", "active", 3),
        ]
    facts = db.connection.execute(
        "SELECT detector_version,status,input_json FROM detector_runs WHERE producer=? ORDER BY id",
        ("mate-in-one",),
    ).fetchall()
    assert [row["detector_version"] for row in facts] == ["v1", "v2", "v1"]
    assert [row["status"] for row in facts] == ["superseded", "superseded", "active"]
    assert json.loads(facts[-1]["input_json"])["detector_input"]["pipeline_generation"] == 3
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM mapping_runs WHERE status=? AND producer=?",
            ("active", "mate-in-one-mapper"),
        ).fetchone()[0]
        == 1
    )
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 1
    assert process_pipeline(db, base, transport=network)["games"] == []
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 3


def test_missing_openings_reprocess_when_dataset_arrives(tmp_path, monkeypatch):
    from chess_coach.openings import import_openings

    db, config, network, _ = setup(tmp_path, monkeypatch, count=1)
    config = replace(config, opening_version="fixture", opening_source="fixture://opening")
    first = process_pipeline(db, config, transport=network)
    assert first["games"][0]["stages"][2]["detail"] == "opening_dataset_missing"
    assert db.connection.execute("SELECT COUNT(*) FROM opening_runs").fetchone()[0] == 0
    path = tmp_path / "openings.tsv"
    path.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, path, version="fixture", source_url="fixture://opening")
    second = process_pipeline(db, config, transport=network)
    stages = second["games"][0]["stages"]
    assert stages[2]["status"] == "complete" and not stages[2]["replayed"]
    assert stages[0]["replayed"] and stages[1]["replayed"] and stages[3]["replayed"]
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 1


def test_game_failure_is_isolated_and_retried_safely(tmp_path, monkeypatch):
    from chess_coach import pipeline_work

    db, config, network, _ = setup(tmp_path, monkeypatch, count=2)
    original = pipeline_work.analyze_game

    def fail_first(db, game_id, *args, **kwargs):
        if game_id == 1:
            raise RuntimeError("sensitive original details")
        return original(db, game_id, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline_work, "analyze_game", fail_first)
        result = process_pipeline(db, config, transport=network)
    assert result["games"][0]["stages"][0]["status"] == "failed"
    assert result["games"][1]["stages"][0]["status"] == "complete"
    assert "sensitive" not in json.dumps(result)
    retried = process_pipeline(db, config, transport=network)
    assert len(retried["games"]) == 1 and retried["games"][0]["game_id"] == 1
    assert retried["games"][0]["stages"][0]["status"] == "complete"
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 2


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


def test_status_is_read_only_and_cli_uses_private_environment(tmp_path, monkeypatch, capsys):
    from argparse import Namespace

    from chess_coach import cli_pipeline
    from chess_coach.pipeline_status import pipeline_status

    db, config, network, _ = setup(tmp_path, monkeypatch, count=1)
    process_pipeline(db, config, transport=network)
    before = db.connection.total_changes
    status = pipeline_status(db)
    assert db.connection.total_changes == before
    assert status["counts"] == {"complete": 3, "skipped": 1}
    assert all(
        set(row) == {"game_id", "stage", "status", "detail", "updated_at"}
        for row in status["stages"]
    )
    assert "learner" not in json.dumps(status).lower()
    cli_pipeline.handle_pipeline_status(db, Namespace())
    assert json.loads(capsys.readouterr().out) == status
    monkeypatch.setenv("LICHESS_USERNAME", "synthetic-user")
    monkeypatch.setenv("LICHESS_API_TOKEN", "synthetic-secret")
    seen = {}

    def fake_process(db, config, *, token):
        seen.update(learner=config.learner, token=token)
        return {"sync": {"status": "complete"}, "games": [], "mastery": []}

    monkeypatch.setattr(cli_pipeline, "process_pipeline", fake_process)
    from chess_coach.cli_parser import build_parser

    args = build_parser().parse_args(["process-pipeline"])
    cli_pipeline.handle_process_pipeline(db, args)
    printed = capsys.readouterr().out
    assert seen == {"learner": "synthetic-user", "token": "synthetic-secret"}
    assert "synthetic-user" not in printed and "synthetic-secret" not in printed
    monkeypatch.delenv("LICHESS_USERNAME")
    with pytest.raises(SystemExit, match="LICHESS_USERNAME"):
        cli_pipeline.handle_process_pipeline(db, args)


def test_position_budget_and_unknown_time_never_produce_candidates(tmp_path, monkeypatch):
    from chess_coach.ingest import ingest_pgn

    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    raw = """[White "Learner"]
[Black "Opponent"]
[Result "1-0"]

1. e4 e5 1-0
"""
    ingest_pgn(db, raw)
    empty = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    over = process_pipeline(db, replace(config, max_positions=1), transport=empty)
    assert over["games"][0]["detail"] == "position_budget_exceeded"
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    done = process_pipeline(db, config, transport=empty)
    assert done["games"][0]["stages"][0]["status"] == "complete"
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM detector_runs WHERE producer=?", ("mate-in-one",)
        ).fetchone()[0]
        == 0
    )


def test_engine_configuration_reprocesses_only_dependent_stages(tmp_path, monkeypatch):
    db, config, network, _ = setup(tmp_path, monkeypatch, count=1)
    first = process_pipeline(db, config, transport=network)
    assert first["games"][0]["stages"][0]["status"] == "complete"
    before = evidence_ids(db, "mate-in-one-mapper")
    before_fork = evidence_ids(db, "fork-opportunity-mapper")
    assert len(before) == 1
    review_evidence(db, before[0], decision="accept", actor="fixture-reviewer")
    second = process_pipeline(db, replace(config, nodes=200), transport=network)
    stages = second["games"][0]["stages"]
    assert not stages[0]["replayed"] and stages[1]["replayed"] and stages[2]["replayed"]
    assert not stages[3]["replayed"]
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 2
    assert db.connection.execute("SELECT COUNT(*) FROM structure_runs").fetchone()[0] == 1
    assert evidence_ids(db, "mate-in-one-mapper") == before
    mate = inspect_evidence(db, before[0])
    assert mate["lifecycle_status"] == "active" and mate["review_status"] == "accepted"
    after_fork = evidence_ids(db, "fork-opportunity-mapper")
    assert len(before_fork) == 1 and len(after_fork) == 2
    statuses = db.connection.execute(
        "SELECT r.status FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE e.id IN (?,?) ORDER BY e.id",
        (after_fork[0], after_fork[1]),
    ).fetchall()
    assert [row[0] for row in statuses] == ["superseded", "active"]


def test_v12_migration_adds_pipeline_without_losing_existing_history(monkeypatch):
    from chess_coach import db_recent

    db = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_pipeline_stages", lambda connection: None)
        patch.setattr(db_recent, "add_pipeline_cooldown", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=12")
    db.connection.execute('INSERT INTO games(pgn,white,black,result) VALUES ("raw","A","B","*")')
    db.connection.commit()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 23
    assert db.connection.execute("SELECT pgn FROM games").fetchone()[0] == "raw"
    for table in ("opening_runs", "structure_runs"):
        assert "pipeline_generation" in {
            row[1] for row in db.connection.execute(f"PRAGMA table_info({table})")
        }
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_network_logging_never_exposes_account_or_token(tmp_path, monkeypatch, caplog):
    import logging

    db, config, network, _ = setup(tmp_path, monkeypatch, count=1)
    with caplog.at_level(logging.DEBUG):
        result = process_pipeline(db, config, token="synthetic-secret", transport=network)
    assert result["sync"]["games"] == 1
    assert "synthetic-secret" not in caplog.text
    assert "/games/user/learner" not in caplog.text.lower()


@pytest.mark.parametrize("failure", ["oversized", "engine"])
def test_failed_first_game_cannot_starve_later_games(tmp_path, monkeypatch, failure):
    from chess_coach import pipeline_work
    from chess_coach.ingest import ingest_pgn

    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    raw = """[White "Learner"]
[Black "Opponent"]
[Result "1-0"]

1. e4 e5 1-0
"""
    ingest_pgn(db, raw)
    ingest_pgn(db, game("later001", int(time.time()) - 5))
    empty = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    selected = replace(
        config, max_games=1, max_scan=1, max_positions=1 if failure == "oversized" else 10
    )
    original = pipeline_work.analyze_game

    def fail_one(db, game_id, *args, **kwargs):
        if failure == "engine" and game_id == 1:
            raise RuntimeError("synthetic error")
        return original(db, game_id, *args, **kwargs)

    monkeypatch.setattr(pipeline_work, "analyze_game", fail_one)
    first = process_pipeline(db, selected, transport=empty)
    assert first["games"][0]["game_id"] == 1
    second = process_pipeline(db, selected, transport=empty)
    assert second["games"][0]["game_id"] == 2
    assert second["games"][0]["stages"][0]["status"] == "complete"
    ingest_pgn(db, game("later002", int(time.time()) - 2))
    third = process_pipeline(db, selected, transport=empty)
    assert third["games"][0]["game_id"] == 3
    assert all(result["scan"]["examined"] <= 1 for result in (first, second, third))


def test_scan_budget_rotates_past_unmatched_games(tmp_path, monkeypatch):
    from chess_coach.ingest import ingest_pgn

    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    now = int(time.time())
    for i in range(3):
        ingest_pgn(db, game(f"other00{i}", now - i - 1).replace("Learner", "Unrelated"))
    ingest_pgn(db, game("later999", now - 10))
    empty = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    config = replace(config, max_scan=2, max_games=1)
    first = process_pipeline(db, config, transport=empty)
    assert first["games"] == [] and first["scan"]["has_more"]
    second = process_pipeline(db, config, transport=empty)
    assert second["games"][0]["game_id"] == 4 and second["scan"]["examined"] == 2


def test_superseded_outputs_trigger_new_current_generation(tmp_path, monkeypatch):
    from chess_coach.opening_classification import classify_game
    from chess_coach.openings import import_openings
    from chess_coach.structure_episodes import extract_game_episodes
    from chess_coach.tactical_opportunities import record_game_opportunities

    db, config, network, _ = setup(tmp_path, monkeypatch, count=1)
    path = tmp_path / "openings.tsv"
    path.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, path, version="fixture", source_url="fixture://opening")
    config = replace(config, opening_version="fixture", opening_source="fixture://opening")
    process_pipeline(db, config, transport=network)
    extract_game_episodes(db, 1, detector_version="external")
    classify_game(
        db, 1, version="fixture", source_url="fixture://opening", classifier_version="external"
    )
    record_game_opportunities(db, 1, learner="learner", detector_version="external")
    result = process_pipeline(db, config, transport=network)
    stages = result["games"][0]["stages"]
    assert stages[0]["replayed"] and all(not item["replayed"] for item in stages[1:])
    for table, column, expected in (
        ("structure_runs", "detector_version", config.structure_version),
        ("opening_runs", "classifier_version", config.classifier_version),
    ):
        row = db.connection.execute(
            f'SELECT {column},pipeline_generation FROM {table} WHERE status="active"'
        ).fetchone()
        assert tuple(row) == (expected, 2)
    row = db.connection.execute(
        'SELECT detector_version,input_json FROM detector_runs WHERE status="active" AND producer="mate-in-one"'
    ).fetchone()
    assert row["detector_version"] == config.tactical_version
    assert json.loads(row["input_json"])["detector_input"]["pipeline_generation"] == 2
    assert process_pipeline(db, config, transport=network)["games"] == []


def test_external_engine_output_rechecks_tactical_without_rerunning_analysis(tmp_path, monkeypatch):
    from chess_coach.analysis import analyze_game

    db, config, network, _ = setup(tmp_path, monkeypatch, count=1)
    process_pipeline(db, config, transport=network)
    analyze_game(db, 1, sys.executable, nodes=101)
    result = process_pipeline(db, config, transport=network)
    stages = result["games"][0]["stages"]
    assert stages[0]["replayed"] and stages[1]["replayed"] and stages[2]["replayed"]
    assert stages[3]["status"] == "complete" and not stages[3]["replayed"]
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 2


def test_sync_failure_and_interruption_health_survive_restart(tmp_path, monkeypatch):
    from chess_coach.pipeline_status import pipeline_status

    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    denied = httpx.MockTransport(lambda request: httpx.Response(403))
    result = process_pipeline(db, config, transport=denied)
    assert result["status"] == "failed" and result["sync"]["detail"] == "sync_failed"
    path = db.path
    db.close()
    reopened = Database(path)
    health = pipeline_status(reopened)["health"]
    assert health["status"] == "failed" and health["sync_status"] == "failed"
    assert health["sync_detail"] == "sync_failed" and health["finished_at"] and health["sync_at"]

    def interrupt(request):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        process_pipeline(reopened, config, transport=httpx.MockTransport(interrupt))
    health = pipeline_status(reopened)["health"]
    assert health["status"] == "running" and health["sync_status"] == "pending"
    assert health["finished_at"] is None


def test_retry_after_is_honored_and_request_count_is_actual(tmp_path, monkeypatch):
    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    sleeps = []
    now = datetime.now(UTC)

    def clock():
        return now

    def sleep(seconds):
        nonlocal now
        sleeps.append(seconds)
        now += timedelta(seconds=seconds)

    monkeypatch.setattr("chess_coach.pipeline_network_budget.time.sleep", sleep)
    calls = []

    def response(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "120"})
        return httpx.Response(200, text="")

    result = process_pipeline(
        db,
        replace(config, network_sleep=120, network_seconds=180),
        transport=httpx.MockTransport(response),
        clock=clock,
    )
    assert sleeps == [120]
    assert result["sync"]["requests"] == len(calls)
    assert result["sync"]["requests"] > result["sync"]["windows"]
    assert (
        db.connection.execute("SELECT retry_until FROM pipeline_health WHERE id=1").fetchone()[0]
        is None
    )


def test_game_selection_error_is_sanitized_and_other_games_continue(tmp_path, monkeypatch):
    from chess_coach import pipeline_scan_item

    db, config, network, _ = setup(tmp_path, monkeypatch, count=2)
    original = pipeline_scan_item.game_input

    def broken(db, game_id):
        if game_id == 1:
            raise RuntimeError("synthetic private detail")
        return original(db, game_id)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline_scan_item, "game_input", broken)
        result = process_pipeline(db, config, transport=network)
    assert result["games"][0]["detail"] == "game_processing_failed"
    assert result["games"][1]["stages"][0]["status"] == "complete"
    assert "synthetic private detail" not in json.dumps(result)
    retried = process_pipeline(db, config, transport=network)
    assert retried["games"][0]["game_id"] == 1
    assert (
        db.connection.execute(
            'SELECT status FROM pipeline_stages WHERE game_id=1 AND stage="input"'
        ).fetchone()[0]
        == "complete"
    )


def test_oversized_network_response_stops_without_import(tmp_path, monkeypatch):
    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    calls = []

    def oversized(request):
        calls.append(request)
        return httpx.Response(200, content=b"x" * 17)

    result = process_pipeline(
        db, replace(config, network_bytes=16), transport=httpx.MockTransport(oversized)
    )
    assert result["sync"] == {"status": "partial", "detail": "network_budget_exhausted"}
    assert (
        len(calls) == 1 and db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
    )


def test_schema_upgrade_failure_rolls_back_pipeline_migration(monkeypatch):
    from chess_coach import db_recent
    from chess_coach.pipeline_schema import add_pipeline_stages

    db = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_pipeline_stages", lambda connection: None)
        patch.setattr(db_recent, "add_pipeline_cooldown", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=12")
    db.connection.commit()

    def fail(connection):
        add_pipeline_stages(connection)
        raise RuntimeError("injected")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_pipeline_stages", fail)
        with pytest.raises(RuntimeError, match="injected"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 12
    assert (
        db.connection.execute(
            'SELECT name FROM sqlite_master WHERE name="pipeline_stages"'
        ).fetchone()
        is None
    )
    assert "pipeline_generation" not in {
        row[1] for row in db.connection.execute("PRAGMA table_info(structure_runs)")
    }
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_only_timed_learner_moves_generate_tactical_facts(tmp_path, monkeypatch):
    from chess_coach.ingest import ingest_pgn

    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    now = datetime.now(UTC)
    raw = f"""[White "Learner"]
[Black "Opponent"]
[UTCDate "{now:%Y.%m.%d}"]
[UTCTime "{now:%H:%M:%S}"]
[Result "1-0"]

1. e4 e5 1-0
"""
    ingest_pgn(db, raw)
    empty = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    result = process_pipeline(db, config, transport=empty)
    assert result["games"][0]["stages"][3]["status"] == "complete"
    plies = [
        row[0]
        for row in db.connection.execute(
            "SELECT p.ply FROM detector_runs d JOIN positions p ON p.id=d.position_id WHERE d.producer=?",
            ("mate-in-one",),
        )
    ]
    assert plies == [1]


@pytest.mark.parametrize("interrupted_stage", ["structures", "opening", "tactical"])
def test_superseded_interrupted_generation_advances_safely(
    tmp_path, monkeypatch, interrupted_stage
):
    from chess_coach import pipeline_stage
    from chess_coach.opening_classification import classify_game
    from chess_coach.openings import import_openings
    from chess_coach.structure_episodes import extract_game_episodes
    from chess_coach.tactical_opportunities import record_game_opportunities

    db, config, network, _ = setup(tmp_path, monkeypatch, count=1)
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
    if interrupted_stage == "structures":
        extract_game_episodes(db, 1, detector_version="external")
    elif interrupted_stage == "opening":
        classify_game(
            db, 1, version="fixture", source_url="fixture://opening", classifier_version="external"
        )
    else:
        # A superseded default fact can be replaced using the pending generation.
        record_game_opportunities(db, 1, learner="learner", detector_version="external")
    result = process_pipeline(db, config, transport=network)
    stage = next(
        item for item in result["games"][0]["stages"] if item["stage"] == interrupted_stage
    )
    assert stage["status"] == "complete"
    row = db.connection.execute(
        "SELECT generation,status FROM pipeline_stages WHERE stage=?", (interrupted_stage,)
    ).fetchone()
    expected = 1 if interrupted_stage == "tactical" else 2
    assert tuple(row) == (expected, "complete")


def test_tactical_generation_superseded_after_interruption_advances(tmp_path, monkeypatch):
    from chess_coach import pipeline_stage
    from chess_coach.ingest import ingest_pgn
    from chess_coach.tactical_opportunities import record_game_opportunities

    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    ingest_pgn(db, game("local001", int(time.time()) - 5))
    record_game_opportunities(db, 1, learner="learner", detector_version=config.tactical_version)
    record_game_opportunities(db, 1, learner="learner", detector_version="external1")
    empty = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    original = pipeline_stage.checkpoint

    def interrupt(connection, game_id, stage, *args, **kwargs):
        if stage == "tactical":
            raise KeyboardInterrupt()
        return original(connection, game_id, stage, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(pipeline_stage, "checkpoint", interrupt)
        with pytest.raises(KeyboardInterrupt):
            process_pipeline(db, config, transport=empty)
    generation_one = db.connection.execute(
        'SELECT input_json FROM detector_runs WHERE status="active" AND producer="mate-in-one"'
    ).fetchone()[0]
    assert json.loads(generation_one)["detector_input"]["pipeline_generation"] == 1
    record_game_opportunities(db, 1, learner="learner", detector_version="external2")
    result = process_pipeline(db, config, transport=empty)
    assert result["games"][0]["stages"][3]["status"] == "complete"
    assert (
        db.connection.execute(
            'SELECT generation FROM pipeline_stages WHERE stage="tactical"'
        ).fetchone()[0]
        == 2
    )
    current = db.connection.execute(
        'SELECT input_json FROM detector_runs WHERE status="active" AND producer="mate-in-one"'
    ).fetchone()[0]
    assert json.loads(current)["detector_input"]["pipeline_generation"] == 2


def test_v13_upgrade_preserves_curriculum_cursor_revision_and_indexes(monkeypatch):
    from chess_coach import db_recent
    from chess_coach.curriculum_cursor import new_state, resume_state
    from chess_coach.curriculum_cursor_codec import decode_cursor, encode_cursor

    db = Database(":memory:")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_pipeline_stages", lambda connection: None)
        patch.setattr(db_recent, "add_pipeline_cooldown", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=13")
    db.connection.execute(
        "INSERT INTO opening_datasets(version,source_url) VALUES (?,?)",
        ("legacy", "fixture://legacy"),
    )
    db.connection.execute(
        'INSERT INTO games(pgn,white,black,result) VALUES ("fixture","A","B","*")'
    )
    db.connection.commit()
    before = tuple(
        db.connection.execute(
            "SELECT revision,cursor_key FROM curriculum_source_revision"
        ).fetchone()
    )
    indexes = [
        tuple(row)
        for row in db.connection.execute(
            'SELECT name,sql FROM sqlite_master WHERE type="index" AND (name LIKE "idx_curriculum_%" OR name="idx_puzzles_curriculum") ORDER BY name'
        )
    ]
    assert any(row[0] == "idx_puzzles_curriculum" for row in indexes)
    state = new_state(db, "learner", "fixture", 10, 10, datetime.now(UTC))
    token = encode_cursor(db, state)
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 23
    assert db.connection.execute("SELECT content_revision FROM opening_datasets").fetchone()[0] == 0
    assert (
        tuple(
            db.connection.execute(
                "SELECT revision,cursor_key FROM curriculum_source_revision"
            ).fetchone()
        )
        == before
    )
    assert [
        tuple(row)
        for row in db.connection.execute(
            'SELECT name,sql FROM sqlite_master WHERE type="index" AND (name LIKE "idx_curriculum_%" OR name="idx_puzzles_curriculum") ORDER BY name'
        )
    ] == indexes
    decoded = decode_cursor(db, token)
    assert decoded == state
    assert resume_state(db, decoded, "learner", "fixture", 10, 10, None)[0] == state
    for table in ("opening_runs", "structure_runs"):
        assert "pipeline_generation" in {
            row[1] for row in db.connection.execute(f"PRAGMA table_info({table})")
        }
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize("enforce", [True, False])
def test_real_slow_stream_is_cancelled_at_total_deadline(tmp_path, monkeypatch, enforce):
    import signal
    import socket
    import threading
    from contextlib import nullcontext
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    from chess_coach import pipeline_network
    from chess_coach.lichess import LichessClient, LichessError
    from chess_coach.pipeline_network import BudgetExceeded, sync_games

    disconnected = threading.Event()
    received = threading.Event()
    waiting = threading.Event()

    class SlowStream(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Length", "2")
            self.end_headers()
            try:
                self.wfile.write(b"x")
                self.wfile.flush()
                self.connection.settimeout(10)
                if self.connection.recv(1, socket.MSG_PEEK) == b"":
                    disconnected.set()
            except OSError:
                disconnected.set()

        def log_message(self, format, *args):
            pass

    original_iter = httpx.Response.iter_raw

    def observed_iter(response, *args, **kwargs):
        for chunk in original_iter(response, *args, **kwargs):
            received.set()
            yield chunk
            time.sleep(1.5)
            waiting.set()

    monkeypatch.setattr(httpx.Response, "iter_raw", observed_iter)
    if not enforce:
        monkeypatch.setattr(pipeline_network, "network_deadline", lambda seconds: nullcontext())
    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowStream)
    server.daemon_threads = True
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    old_handler = signal.getsignal(signal.SIGALRM)
    try:
        monkeypatch.setattr(
            LichessClient, "endpoint", f"http://127.0.0.1:{server.server_port}/{{username}}"
        )
        db = Database(tmp_path / "slow.sqlite")
        db.initialize()
        config = PipelineConfig(
            learner="synthetic", network_seconds=4.0, network_timeout=10, network_retries=0
        )
        start = time.monotonic()
        with pytest.raises(BudgetExceeded if enforce else LichessError):
            sync_games(db, config)
        elapsed = time.monotonic() - start
        assert received.is_set() and waiting.is_set() and disconnected.wait(1)
        assert (elapsed < 5.0) if enforce else (elapsed > 4.8)
        assert not db.connection.in_transaction
        assert db.connection.execute("SELECT COUNT(*) FROM games").fetchone()[0] == 0
        assert signal.getsignal(signal.SIGALRM) == old_handler
        assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
    assert not thread.is_alive()


def test_network_deadline_refuses_non_main_threads_and_existing_timers():
    import signal
    import threading

    from chess_coach.pipeline_network_deadline import WorkerContextError, network_deadline

    errors = []

    def worker():
        try:
            with network_deadline(0.1):
                pass
        except WorkerContextError as exc:
            errors.append(str(exc))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=2)
    assert errors == ["network worker requires a dedicated process main thread"]
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
    previous = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, lambda *_: None)
    signal.setitimer(signal.ITIMER_REAL, 5)
    try:
        with pytest.raises(WorkerContextError, match="active process timer"), network_deadline(0.1):
            pass
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def test_threaded_worker_reports_safe_failure_without_network(tmp_path):
    import threading

    from chess_coach.ingest import ingest_pgn
    from chess_coach.pipeline_status import pipeline_status

    path = tmp_path / "threaded.sqlite"
    db = Database(path)
    db.initialize()
    ingest_pgn(db, game("threaded01", int(time.time()) - 5))
    db.close()
    calls = []
    results = []

    def transport(request):
        calls.append(request)
        return httpx.Response(200, text="")

    def worker():
        local_db = Database(path)
        try:
            results.append(
                process_pipeline(
                    local_db,
                    PipelineConfig(learner="synthetic"),
                    transport=httpx.MockTransport(transport),
                )
            )
        finally:
            local_db.close()

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(timeout=5)
    assert not thread.is_alive() and not calls
    assert results[0]["sync"] == {"status": "failed", "detail": "worker_process_required"}
    assert results[0]["games"] == []
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0
    health = pipeline_status(db)["health"]
    assert health["sync_status"] == "failed" and health["sync_detail"] == "worker_process_required"
    db.close()


def test_changed_settings_require_a_fresh_bounded_scan(tmp_path, monkeypatch):
    from chess_coach.ingest import ingest_pgn
    from chess_coach.openings import import_openings

    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    now = int(time.time())
    ingest_pgn(db, game("fixture01", now - 10))
    ingest_pgn(db, game("fixture02", now - 20))
    network = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    openings = tmp_path / "openings.tsv"
    openings.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, openings, version="fixture", source_url="fixture://opening")
    config = replace(
        config,
        deep_enabled=False,
        max_games=1,
        max_scan=1,
        opening_version="fixture",
        opening_source="fixture://opening",
    )
    first = process_pipeline(db, config, transport=network)
    assert first["games"][0]["game_id"] == 1 and first["status"] == "partial"
    changed = replace(config, nodes=config.nodes + 1)
    second = process_pipeline(db, changed, transport=network)
    assert second["games"][0]["game_id"] == 1 and second["status"] == "partial"
    path = db.path
    db.close()
    db = Database(path)
    third = process_pipeline(db, changed, transport=network)
    assert third["games"][0]["game_id"] == 2 and third["status"] == "complete"
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 3


@pytest.mark.parametrize("status,exit_code", [("failed", 1), ("partial", 0), ("complete", 0)])
def test_pipeline_cli_exit_status_matches_failure(tmp_path, monkeypatch, capsys, status, exit_code):
    from chess_coach import cli_pipeline
    from chess_coach.cli_parser import build_parser

    db, _, _, _ = setup(tmp_path, monkeypatch, count=0)
    monkeypatch.setattr(
        cli_pipeline, "process_pipeline", lambda *args, **kwargs: {"status": status}
    )
    args = build_parser().parse_args(["process-pipeline", "learner"])
    if exit_code:
        with pytest.raises(SystemExit) as error:
            cli_pipeline.handle_process_pipeline(db, args)
        assert error.value.code == exit_code
    else:
        cli_pipeline.handle_process_pipeline(db, args)
    assert json.loads(capsys.readouterr().out) == {"status": status}


def test_scan_fingerprint_tracks_output_settings_but_not_worker_budgets(tmp_path, monkeypatch):
    from chess_coach.pipeline_inputs import scan_input

    db, _, _, _ = setup(tmp_path, monkeypatch, count=0)
    config = PipelineConfig(learner="learner")
    original = scan_input(db, config, "engine-a")
    changes = {
        "max_positions": 10,
        "nodes": 11,
        "seconds_per_position": 2.0,
        "threads": 2,
        "hash_mb": 128,
        "opening_version": "v2",
        "opening_source": "fixture://other",
        "structure_version": "v2",
        "classifier_version": "v2",
        "ontology_version": "v2",
        "tactical_version": "v2",
    }
    assert all(
        scan_input(db, replace(config, **{key: value}), "engine-a") != original
        for key, value in changes.items()
    )
    assert scan_input(db, config, "engine-b") != original
    assert (
        scan_input(db, replace(config, max_games=1, max_scan=2, network_requests=3), "engine-a")
        == original
    )


def test_opening_dataset_append_restarts_bounded_scan(tmp_path, monkeypatch):
    from chess_coach.ingest import ingest_pgn
    from chess_coach.openings import import_openings

    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    now = int(time.time())
    ingest_pgn(db, game("fixture01", now - 10))
    ingest_pgn(db, game("fixture02", now - 20))
    openings = tmp_path / "openings.tsv"
    openings.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, openings, version="fixture", source_url="fixture://opening")
    config = replace(
        config,
        deep_enabled=False,
        max_games=1,
        max_scan=1,
        opening_version="fixture",
        opening_source="fixture://opening",
    )
    network = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    first = process_pipeline(db, config, transport=network)
    assert first["games"][0]["game_id"] == 1 and first["status"] == "partial"
    prior_revision = db.connection.execute(
        "SELECT content_revision FROM opening_datasets"
    ).fetchone()[0]
    import_openings(db, openings, version="fixture", source_url="fixture://opening")
    assert (
        db.connection.execute("SELECT content_revision FROM opening_datasets").fetchone()[0]
        == prior_revision
    )
    openings.write_text("eco\tname\tmoves\nC20\tOther\td4 d5\n")
    import_openings(db, openings, version="fixture", source_url="fixture://opening")
    assert (
        db.connection.execute("SELECT content_revision FROM opening_datasets").fetchone()[0]
        > prior_revision
    )
    second = process_pipeline(db, config, transport=network)
    assert second["games"][0]["game_id"] == 1 and second["status"] == "partial"
    third = process_pipeline(db, config, transport=network)
    assert third["games"][0]["game_id"] == 2 and third["status"] == "complete"


def test_opening_revision_rolls_back_with_failed_import(tmp_path, monkeypatch):
    from chess_coach.openings import import_openings

    db, _, _, _ = setup(tmp_path, monkeypatch, count=0)
    openings = tmp_path / "openings.tsv"
    openings.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, openings, version="fixture", source_url="fixture://opening")
    before = db.connection.execute("SELECT content_revision FROM opening_datasets").fetchone()[0]
    nodes = db.connection.execute("SELECT COUNT(*) FROM opening_nodes").fetchone()[0]
    openings.write_text("eco\tname\tmoves\nC20\tOther\td4 d5\nC20\t\te4 e5\n")
    with pytest.raises(ValueError):
        import_openings(db, openings, version="fixture", source_url="fixture://opening")
    assert (
        db.connection.execute("SELECT content_revision FROM opening_datasets").fetchone()[0]
        == before
    )
    assert db.connection.execute("SELECT COUNT(*) FROM opening_nodes").fetchone()[0] == nodes


def test_opening_dataset_change_during_scan_prevents_false_completion(tmp_path, monkeypatch):
    from chess_coach import pipeline
    from chess_coach.ingest import ingest_pgn
    from chess_coach.openings import import_openings

    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    ingest_pgn(db, game("fixture01", int(time.time()) - 10))
    openings = tmp_path / "openings.tsv"
    openings.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, openings, version="fixture", source_url="fixture://opening")
    config = replace(
        config, deep_enabled=False, opening_version="fixture", opening_source="fixture://opening"
    )
    original = pipeline.process_game

    def process_then_import(*args):
        result = original(*args)
        openings.write_text("eco\tname\tmoves\nC20\tOther\td4 d5\n")
        import_openings(db, openings, version="fixture", source_url="fixture://opening")
        return result

    network = httpx.MockTransport(lambda request: httpx.Response(200, text=""))
    with monkeypatch.context() as patch:
        patch.setattr(pipeline, "process_game", process_then_import)
        result = process_pipeline(db, config, transport=network)
    assert result["status"] == "partial" and result["scan"]["has_more"]
    replay = process_pipeline(db, config, transport=network)
    assert replay["games"][0]["game_id"] == 1 and replay["status"] == "complete"


def test_worker_sends_application_identity_and_existing_auth_headers(tmp_path, monkeypatch):
    from chess_coach import __version__

    db, config, _, _ = setup(tmp_path, monkeypatch, count=0)
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, text="")

    result = process_pipeline(
        db, config, token="synthetic-token", transport=httpx.MockTransport(handle)
    )
    assert result["sync"]["status"] in {"complete", "partial"}
    assert requests
    for request in requests:
        assert request.headers["user-agent"] == (
            f"chess-knowledge-coach/{__version__} (+https://github.com/pavelkrotkov/chess-knowledge-coach)"
        )
        assert request.headers["accept"] == "application/x-chess-pgn"
        assert request.headers["authorization"] == "Bearer synthetic-token"
