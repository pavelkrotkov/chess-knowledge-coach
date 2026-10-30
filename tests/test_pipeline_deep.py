"""Automatic deep work preserves cheap analysis, fairness and private state."""

import json
import sys
from dataclasses import replace

import chess.engine
import httpx
import pytest

from chess_coach.analysis import merge_analysis_outputs
from chess_coach.db import Database
from chess_coach.decision_inspection import inspect_decision
from chess_coach.deep_selection_views import show_selection
from chess_coach.pipeline import process_pipeline
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_status import pipeline_status
from tests.test_deep_execution import DeepEngine
from tests.test_deep_selection import LEARNER, OPPONENT, Engine, setup_game


def network():
    return httpx.MockTransport(lambda request: httpx.Response(200, text=""))


def config(learner=LEARNER):
    return PipelineConfig(
        learner=learner,
        engine_path=sys.executable,
        nodes=100,
        deep_max_games=1,
        deep_per_game=3,
        deep_max_jobs=1,
        deep_nodes=1000,
        deep_seconds=0.5,
    )


def engines(monkeypatch, db):
    calls = []

    def start(_binary, timeout=None):
        if timeout is None:
            return Engine()
        result = DeepEngine(db)
        calls.append(result)
        return result

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", start)
    return calls


def test_round_robin_retains_pending_and_reuses_current_results(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "fair.sqlite", monkeypatch, count=2)
    engines(monkeypatch, db)
    settings = config()
    cheap = db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0]
    for _ in range(4):
        result = process_pipeline(db, settings, transport=network())
        assert result["deep"]["processed"] == 1
        assert result["deep"]["capped"] and result["deep"]["pending"] >= 1
        assert result["status"] == "partial"
    first, second = [show_selection(db, i, LEARNER) for i in (1, 2)]
    assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 2
    assert all(
        sum(item["status"] == "pending" for item in s["items"]) == 1 for s in (first, second)
    )
    assert pipeline_status(db, LEARNER)["deep"]["counts"]["pending"] == 2
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == cheap
    for _ in range(2):
        process_pipeline(db, settings, transport=network())
    before = db.connection.execute("SELECT COUNT(*) FROM deep_analysis_attempts").fetchone()[0]
    replay = process_pipeline(db, settings, transport=network())
    assert replay["deep"]["processed"] == 0
    assert (
        db.connection.execute("SELECT COUNT(*) FROM deep_analysis_attempts").fetchone()[0] == before
    )
    assert show_selection(db, 1, LEARNER)["selection_id"] == first["selection_id"]
    assert show_selection(db, 2, LEARNER)["selection_id"] == second["selection_id"]
    current = inspect_decision(db, first["items"][0]["position_id"], learner=LEARNER)
    assert current["deep"]["status"] in {"complete", "unstable"}
    changed = process_pipeline(db, replace(settings, deep_nodes=2000), transport=network())
    assert changed["deep"]["processed"] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0] == cheap
    assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 2
    status = pipeline_status(db, LEARNER)["deep"]
    assert status["limits"]["nodes_per_search"] == 2000
    assert LEARNER not in json.dumps(status)


@pytest.mark.parametrize("learner,parity", [(LEARNER, 1), (OPPONENT, 0)])
def test_both_colors_use_reconstructed_game_history(tmp_path, monkeypatch, learner, parity):
    db = setup_game(tmp_path / "colors.sqlite", monkeypatch)
    calls = engines(monkeypatch, db)
    result = process_pipeline(db, config(learner), transport=network())
    assert result["deep"]["processed"] == 1
    selected = show_selection(db, 1, learner)
    assert all(item["ply"] % 2 == parity for item in selected["items"])
    used = next(item for item in selected["items"] if item["status"] != "pending")
    board = calls[0].calls[0][0]
    assert len(board.move_stack) == used["ply"] - 1
    assert calls[0].calls[1][0].move_stack == board.move_stack
    assert inspect_decision(db, used["position_id"], learner=learner)["deep"] is not None


def test_backup_and_merge_fail_closed_for_automatic_deep(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "source.sqlite", monkeypatch)
    engines(monkeypatch, db)
    process_pipeline(db, config(), transport=network())
    backup = Database(tmp_path / "backup.sqlite")
    db.connection.backup(backup.connection)
    assert pipeline_status(backup, LEARNER)["deep"]["counts"]["selected"] == 3
    target = Database(tmp_path / "target.sqlite")
    target.initialize()
    with pytest.raises(ValueError, match="selection or deep history"):
        merge_analysis_outputs(target, backup)
    assert target.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0


def _blocked_pipeline(path, started, release, queue):
    from unittest.mock import patch

    db = Database(path)
    db.initialize()

    class BlockingEngine(DeepEngine):
        def analyse(self, board, limit, multipv, root_moves=None):
            started.set()
            if not release.wait(90):
                raise TimeoutError("synthetic wait")
            return super().analyse(board, limit, multipv, root_moves=root_moves)

    def start(_binary, timeout=None):
        return Engine() if timeout is None else BlockingEngine(db)

    with patch.object(chess.engine.SimpleEngine, "popen_uci", start):
        try:
            queue.put(process_pipeline(db, config(), transport=network()))
        finally:
            db.close()


def test_auto_worker_does_not_delay_real_sync_retry_deadline(tmp_path, monkeypatch):
    import multiprocessing
    import time
    from datetime import UTC, datetime, timedelta

    from chess_coach.pipeline_sync import sync_result

    path = tmp_path / "parallel.sqlite"
    db = setup_game(path, monkeypatch)
    ctx = multiprocessing.get_context("spawn")
    started, release, queue = ctx.Event(), ctx.Event(), ctx.Queue()
    process = ctx.Process(target=_blocked_pipeline, args=(path, started, release, queue))
    process.start()
    try:
        assert started.wait(45)
        deadline = (datetime.now(UTC) + timedelta(seconds=2)).isoformat()
        db.connection.execute("UPDATE pipeline_health SET retry_until=? WHERE id=1", (deadline,))
        db.connection.commit()
        seen = []
        transport = httpx.MockTransport(
            lambda request: (seen.append(True), httpx.Response(200, text=""))[1]
        )
        assert sync_result(db, config(), None, transport, None, retry_only=True) is None
        assert not seen
        time.sleep(2.1)
        response = sync_result(db, config(), None, transport, None, retry_only=True)
        assert response is not None and response["status"] in {"complete", "partial"}
        assert seen and process.is_alive()
        release.set()
        assert queue.get(timeout=60)["deep"]["processed"] == 1
        process.join(20)
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            release.set()
            process.terminate()
            process.join(10)


def test_auto_worker_recovers_interrupted_claim_after_restart(tmp_path, monkeypatch):
    import multiprocessing

    path = tmp_path / "restart.sqlite"
    db = setup_game(path, monkeypatch)
    ctx = multiprocessing.get_context("spawn")
    started, release, queue = ctx.Event(), ctx.Event(), ctx.Queue()
    process = ctx.Process(target=_blocked_pipeline, args=(path, started, release, queue))
    process.start()
    try:
        assert started.wait(45)
        process.terminate()
        process.join(10)
        assert not process.is_alive()
        engines(monkeypatch, db)
        resumed = process_pipeline(db, config(), transport=network())
        assert resumed["deep"]["processed"] == 1
        rows = db.connection.execute(
            "SELECT status FROM deep_analysis_attempts ORDER BY id"
        ).fetchall()
        assert [row[0] for row in rows] == ["interrupted", "complete"]
        assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 1
    finally:
        if process.is_alive():
            process.terminate()
            process.join(10)


def test_source_changes_during_automatic_search_discard_and_reselect(tmp_path, monkeypatch):
    import multiprocessing

    path = tmp_path / "changed.sqlite"
    db = setup_game(path, monkeypatch)
    before = db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
    ctx = multiprocessing.get_context("spawn")
    started, release, queue = ctx.Event(), ctx.Event(), ctx.Queue()
    process = ctx.Process(target=_blocked_pipeline, args=(path, started, release, queue))
    process.start()
    try:
        assert started.wait(45)
        db.connection.execute(
            "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
            ("best",),
        )
        db.connection.commit()
        release.set()
        result = queue.get(timeout=60)
        process.join(20)
        assert process.exitcode == 0
        assert result["deep"]["status"] == "partial"
        assert result["deep"]["detail"] == "selection_changed"
        assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == before
        engines(monkeypatch, db)
        replay = process_pipeline(db, config(), transport=network())
        assert replay["deep"]["processed"] == 1
        assert db.connection.execute("SELECT COUNT(*) FROM deep_selection_runs").fetchone()[0] == 2
    finally:
        if process.is_alive():
            release.set()
            process.terminate()
            process.join(10)


@pytest.mark.parametrize(
    "field,value",
    [
        ("deep_max_jobs", 0),
        ("deep_nodes", 0),
        ("deep_seconds", float("nan")),
        ("deep_multipv", 4),
        ("deep_max_scan", True),
        ("deep_enabled", 1),
    ],
)
def test_automatic_limits_are_validated(field, value):
    with pytest.raises(ValueError):
        replace(config(), **{field: value}).validate()


def test_timeout_leaves_pending_distinct_from_budget_cap(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "timeout.sqlite", monkeypatch)

    def start(_binary, timeout=None):
        return Engine() if timeout is None else DeepEngine(db, mode="timeout")

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", start)
    settings = replace(config(), deep_max_jobs=3)
    result = process_pipeline(db, settings, transport=network())
    assert result["deep"]["processed"] == 1
    assert result["deep"]["insufficient"] == 1 and result["deep"]["pending"] == 2
    assert not result["deep"]["capped"] and result["status"] == "partial"
    engines(monkeypatch, db)
    resumed = process_pipeline(db, settings, transport=network())
    assert resumed["deep"]["processed"] == 2
    assert resumed["deep"]["insufficient"] == 1 and resumed["deep"]["pending"] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM deep_analysis_attempts").fetchone()[0] == 3


def test_automatic_deep_defaults_match_cli():
    from chess_coach.cli_parser import build_parser
    from chess_coach.opening_snapshot import SOURCE, VERSION

    defaults = PipelineConfig(learner=LEARNER)
    args = build_parser().parse_args(["process-pipeline"])
    assert defaults.deep_nodes == args.deep_nodes == 50000
    assert defaults.deep_seconds == args.deep_seconds == 2.0
    assert defaults.deep_max_jobs == args.deep_max_jobs == 4
    assert defaults.deep_multipv == args.deep_multipv == 3
    assert (args.opening_version, args.opening_source) == (VERSION, SOURCE)
    assert args.classifier_version == "1.1.0"


def test_aggregate_completion_waits_for_deep_backlog(tmp_path, monkeypatch):
    from chess_coach.openings import import_openings

    db = setup_game(tmp_path / "complete.sqlite", monkeypatch)
    engines(monkeypatch, db)
    openings = tmp_path / "opening.tsv"
    openings.write_text("eco\tname\tmoves\nC20\tOpen\te4 e5\n")
    import_openings(db, openings, version="fixture", source_url="fixture://opening")
    settings = replace(config(), opening_version="fixture", opening_source="fixture://opening")
    first = process_pipeline(db, settings, transport=network())
    assert first["deep"]["pending"] == 2 and first["status"] == "partial"
    second = process_pipeline(db, settings, transport=network())
    assert second["deep"]["pending"] == 1 and second["status"] == "partial"
    third = process_pipeline(db, settings, transport=network())
    assert third["deep"]["pending"] == 0 and third["deep"]["status"] == "complete"
    assert third["mate"]["capped"] and third["status"] == "partial"
    assert third["mate"]["back_rank"]["attempted"] == 4
    assert third["mate"]["back_rank"]["replayed"] == 4
    assert third["mate"]["back_rank"]["processed"] == 0
    fourth = process_pipeline(db, settings, transport=network())
    assert fourth["deep"]["pending"] == 0 and fourth["deep"]["status"] == "complete"
    assert not fourth["mate"]["capped"] and fourth["status"] == "complete"
    assert fourth["mate"]["back_rank"]["attempted"] == 2
    assert fourth["mate"]["back_rank"]["replayed"] == 2
    assert fourth["mate"]["back_rank"]["processed"] == 0


def test_status_scales_and_preserves_currentness(tmp_path, monkeypatch):
    from chess_coach.deep_selection import select_deep

    db = setup_game(tmp_path / "scaled.sqlite", monkeypatch)
    select_deep(db, [1], learner=LEARNER, per_game=3, total=3)
    connection = db.connection
    connection.execute("CREATE TEMP TABLE original_outputs AS SELECT * FROM engine_outputs")
    connection.execute("DELETE FROM engine_outputs")
    connection.execute(
        'INSERT INTO analysis_runs(game_id,engine,engine_version,config_json) VALUES(1,"other","1","{}")'
    )
    other_run = connection.execute("SELECT MAX(id) FROM analysis_runs").fetchone()[0]
    position_id = connection.execute("SELECT MIN(id) FROM positions").fetchone()[0]
    connection.executemany(
        "INSERT INTO engine_outputs(run_id,position_id) VALUES(?,?)",
        [(other_run, position_id)] * 10000,
    )
    columns = [
        row[1] for row in connection.execute("PRAGMA table_info(engine_outputs)") if row[1] != "id"
    ]
    names = ",".join(columns)
    connection.execute(f"INSERT INTO engine_outputs({names}) SELECT {names} FROM original_outputs")
    connection.commit()
    steps = [0]

    def progress():
        steps[0] += 1
        return steps[0] > 100

    connection.set_progress_handler(progress, 1000)
    try:
        status = pipeline_status(db, LEARNER, include_stages=False)
    finally:
        connection.set_progress_handler(None, 0)
    assert status["deep"]["counts"]["selected"] == 3
    assert status["deep"]["counts"]["pending"] == 3
    assert status["stages"] == []
    assert status["counts"] == pipeline_status(db)["counts"]
    assert (
        pipeline_status(db, "another_learner", include_stages=False)["deep"]["counts"]["selected"]
        == 0
    )
    connection.execute("UPDATE engine_outputs SET decision_fen=NULL WHERE run_id!=?", (other_run,))
    assert (
        pipeline_status(db, LEARNER, include_stages=False)["deep"]["counts"]["stale_selections"]
        == 1
    )
