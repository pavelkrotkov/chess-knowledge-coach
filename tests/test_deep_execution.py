"""Bounded deep work remains separate, resumable and provenance-aware."""

import json
import sys
from typing import Any
from unittest.mock import patch

import chess
import chess.engine
import pytest

from chess_coach.analysis import merge_analysis_outputs
from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.decision_inspection import inspect_decision
from chess_coach.deep_execution_config import DeepOptions
from chess_coach.deep_execution_worker import run_deep
from chess_coach.deep_selection import select_deep
from chess_coach.deep_selection_views import show_selection
from chess_coach.web import create_app
from tests.test_deep_selection import LEARNER, setup_game


class DeepEngine:
    def __init__(self, db=None, *, score=20, mode="normal", name="Synthetic"):
        self.id = {"name": name}
        self.options = {}
        self.db = db
        self.score = score
        self.mode = mode
        self.calls = []
        self.closed = False

    def configure(self, settings):
        self.settings = settings
        if self.db is not None:
            assert not self.db.connection.in_transaction

    def analyse(self, board, limit, multipv, root_moves=None):
        if self.db is not None:
            assert not self.db.connection.in_transaction
        self.calls.append((board.copy(), limit, multipv, root_moves))
        if self.mode == "timeout":
            raise TimeoutError("synthetic timeout")
        choices = root_moves or list(board.legal_moves)[:multipv]
        if self.mode == "partial" and root_moves is None:
            choices = choices[:1]
        values = []
        for rank, move in enumerate(choices, 1):
            score = chess.engine.Mate(3) if self.mode == "mate" else chess.engine.Cp(self.score)
            line = {
                "score": chess.engine.PovScore(score, board.turn),
                "pv": [move],
                "nodes": 200 if root_moves else 100 + rank,
                "depth": 5,
                "time": 0.05,
                "wdl": chess.engine.PovWdl(chess.engine.Wdl(600, 200, 200), board.turn),
            }
            if self.mode == "bound":
                line["lowerbound"] = True
            if self.mode == "empty_pv":
                line["pv"] = []
            values.append(line)
        return values

    def quit(self):
        if self.db is not None:
            assert not self.db.connection.in_transaction
        self.closed = True

    def close(self):
        self.closed = True


def options(**kwargs):
    values: dict[str, Any] = {
        "engine_path": sys.executable,
        "nodes": 1000,
        "seconds": 0.5,
        "multipv": 3,
        "threads": 1,
        "hash_mb": 4,
        "min_depth": 4,
        "max_jobs": 1,
    }
    values.update(kwargs)
    return DeepOptions(**values)


def prepare_selected(path, monkeypatch, *, per_game=3):
    db = setup_game(path, monkeypatch)
    report = select_deep(db, [1], learner=LEARNER, per_game=per_game, total=per_game)
    return db, report["games"][0]["selection_id"]


def use_engine(monkeypatch, engine):
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _binary, timeout: engine)


def test_bounded_execution_preserves_cheap_and_shared_work(tmp_path, monkeypatch):
    db, selection_id = prepare_selected(tmp_path / "deep.sqlite", monkeypatch)
    selection = show_selection(db, 1, LEARNER)
    first = selection["items"][0]
    original_outputs = db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0]
    original_evidence = db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[
        0
    ]
    engine = DeepEngine(db)
    use_engine(monkeypatch, engine)
    result = run_deep(db, selection_id, learner=LEARNER, options=options())
    assert result["status"] == "partial" and len(result["processed"]) == 1
    assert result["counts"]["pending"] == 2 and result["counts"]["complete"] == 1
    assert len(engine.calls) == 2 and engine.closed
    assert engine.calls[0][0].move_stack == engine.calls[1][0].move_stack
    assert engine.calls[0][1].nodes == engine.calls[1][1].nodes == 1000
    assert engine.calls[0][2] == 3 and len(engine.calls[1][3]) == 1
    report = inspect_decision(db, first["position_id"], learner=LEARNER)
    assert report["run"]["id"] == selection["cheap_run_id"]
    assert inspect_decision(db, first["position_id"], learner="default")["deep"] is None
    deep = report["deep"]
    assert deep["status"] == "complete" and len(deep["result"]["alternatives"]) == 3
    assert deep["result"]["best_work"]["nodes"] == 103
    assert deep["result"]["best_work"]["shared_search"] is True
    assert deep["result"]["played_work"]["nodes"] == 200
    assert deep["result"]["played"]["root_move"] == report["played_move"]
    assert "engine_sha256" not in deep["result"]["limits"]
    unrelated = next(
        item["position_id"]
        for item in selection["items"]
        if item["position_id"] != first["position_id"]
    )
    other = inspect_decision(db, unrelated, learner=LEARNER)
    assert other["run"]["id"] == selection["cheap_run_id"]
    assert other["deep"]["status"] == "pending"
    assert (
        db.connection.execute("SELECT COUNT(*) FROM engine_outputs").fetchone()[0]
        == original_outputs
    )
    assert (
        db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0]
        == original_evidence
    )
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_states").fetchone()[0] == 0
    again = run_deep(db, selection_id, learner=LEARNER, options=options(max_jobs=3))
    assert len(again["processed"]) == 2
    assert db.connection.execute("SELECT COUNT(*) FROM deep_analysis_attempts").fetchone()[0] == 3


def test_incomplete_timeout_retry_preserves_attempts(tmp_path, monkeypatch):
    db, selection_id = prepare_selected(tmp_path / "retry.sqlite", monkeypatch, per_game=1)
    use_engine(monkeypatch, DeepEngine(db, mode="timeout"))
    first = run_deep(db, selection_id, learner=LEARNER, options=options())
    assert first["processed"][0]["status"] == "insufficient"
    assert first["processed"][0]["detail"] == "engine_timeout"
    use_engine(monkeypatch, DeepEngine(db))
    replay = run_deep(db, selection_id, learner=LEARNER, options=options())
    assert replay["processed"] == []
    retried = run_deep(db, selection_id, learner=LEARNER, options=options(retry_insufficient=True))
    assert retried["processed"][0]["status"] == "complete"
    assert [
        row[0]
        for row in db.connection.execute(
            "SELECT status FROM deep_analysis_attempts ORDER BY attempt_number"
        )
    ] == ["insufficient", "complete"]
    assert db.connection.execute("SELECT COUNT(*) FROM deep_analysis_jobs").fetchone()[0] == 1


@pytest.mark.parametrize(
    "mode,detail",
    [
        ("partial", "missing_alternatives"),
        ("empty_pv", "invalid_alternatives"),
        ("bound", "incomplete_line"),
    ],
)
def test_unusable_search_is_insufficient(tmp_path, monkeypatch, mode, detail):
    db, selection_id = prepare_selected(tmp_path / "incomplete.sqlite", monkeypatch, per_game=1)
    use_engine(monkeypatch, DeepEngine(db, mode=mode))
    result = run_deep(db, selection_id, learner=LEARNER, options=options())
    assert result["processed"][0]["status"] == "insufficient"
    assert result["processed"][0]["detail"] == detail
    item = show_selection(db, 1, LEARNER)["items"][0]
    assert item["status"] == "insufficient"


def test_native_mate_and_changed_engine_are_incomparable(tmp_path, monkeypatch):
    db, selection_id = prepare_selected(tmp_path / "mate.sqlite", monkeypatch, per_game=1)
    use_engine(monkeypatch, DeepEngine(db, mode="mate", name="Other Synthetic"))
    report = run_deep(db, selection_id, learner=LEARNER, options=options())
    assert report["processed"][0]["status"] == "complete"
    assert report["processed"][0]["comparison"] == "incomparable"
    item = show_selection(db, 1, LEARNER)["items"][0]
    deep = inspect_decision(db, item["position_id"], learner=LEARNER)["deep"]
    assert deep["result"]["best"]["score_kind"] == "mate"
    assert deep["result"]["best"]["score_value"] == 3
    assert deep["result"]["best"]["wdl"] == [600, 200, 200]


def test_stability_only_for_matching_recorded_engine_and_scores(tmp_path, monkeypatch):
    db, selection_id = prepare_selected(tmp_path / "drift.sqlite", monkeypatch, per_game=6)
    use_engine(monkeypatch, DeepEngine(db, score=500))
    result = run_deep(db, selection_id, learner=LEARNER, options=options(max_jobs=6))
    selected = show_selection(db, 1, LEARNER)["items"]
    first_move = next(item for item in selected if item["ply"] == 1)
    deep = inspect_decision(db, first_move["position_id"], learner=LEARNER)["deep"]
    assert deep["status"] == "unstable" and deep["comparison"] == "comparable"
    assert any(item["status"] == "unstable" for item in result["processed"])
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0


def test_browser_and_cli_report_deep_without_exposing_engine_identity(
    tmp_path, monkeypatch, capsys
):
    db_path = tmp_path / "web.sqlite"
    db, selection_id = prepare_selected(db_path, monkeypatch, per_game=1)
    use_engine(monkeypatch, DeepEngine(db))
    monkeypatch.setenv("LICHESS_USERNAME", LEARNER)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(db_path),
            "run-deep",
            str(selection_id),
            "--engine-path",
            sys.executable,
            "--nodes",
            "1000",
            "--seconds",
            "0.5",
            "--hash-mb",
            "4",
            "--max-jobs",
            "1",
        ],
    )
    main()
    output = capsys.readouterr().out
    assert json.loads(output)["processed"][0]["status"] == "complete"
    assert LEARNER not in output and "fingerprint" not in output and "sha256" not in output
    item = show_selection(db, 1, LEARNER)["items"][0]
    app = create_app(
        db_path=db_path,
        subject=LEARNER,
        actor="fixture-reviewer",
        corpus="test",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert (
        client.get(
            f"/decisions/{item['position_id']}", base_url="https://coach.invalid"
        ).status_code
        == 403
    )
    page = client.get(
        f"/decisions/{item['position_id']}",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture-login"},
    )
    assert page.status_code == 200 and b"Deep analysis" in page.data and b"shared" in page.data
    assert b"not proof" in page.data


def test_handoff_rejects_orphan_deep_rows_even_without_selection_history(tmp_path):
    source = Database(tmp_path / "source.sqlite")
    target = Database(tmp_path / "target.sqlite")
    source.initialize()
    target.initialize()
    source.connection.execute("PRAGMA foreign_keys=OFF")
    source.connection.execute(
        "INSERT INTO deep_analysis_jobs(selection_id,position_id,config_fingerprint,config_json,status) VALUES(1,1,'fixture','{}','pending')"
    )
    source.connection.commit()
    source.connection.execute("PRAGMA foreign_keys=ON")
    with pytest.raises(ValueError, match="selection or deep history"):
        merge_analysis_outputs(target, source)
    assert target.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == 0


def _blocked_worker(path, selection_id, started, release, queue):
    db = Database(path)
    db.initialize()

    class BlockingEngine(DeepEngine):
        def analyse(self, board, limit, multipv, root_moves=None):
            started.set()
            if not release.wait(25):
                raise TimeoutError("synthetic wait")
            return super().analyse(board, limit, multipv, root_moves=root_moves)

    with patch.object(
        chess.engine.SimpleEngine, "popen_uci", lambda _binary, timeout: BlockingEngine(db)
    ):
        try:
            queue.put(run_deep(db, selection_id, learner=LEARNER, options=options()))
        finally:
            db.close()


def test_real_process_deep_lock_allows_concurrent_sync_retry(tmp_path, monkeypatch):
    import multiprocessing
    from datetime import UTC, datetime, timedelta

    import httpx

    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_health import start_run
    from chess_coach.pipeline_sync import sync_result

    path = tmp_path / "concurrent.sqlite"
    db, selection_id = prepare_selected(path, monkeypatch, per_game=1)
    start_run(db)
    past = (datetime.now(UTC) - timedelta(minutes=1)).isoformat()
    db.connection.execute("UPDATE pipeline_health SET retry_until=? WHERE id=1", (past,))
    db.connection.commit()
    ctx = multiprocessing.get_context("spawn")
    started, release, queue = ctx.Event(), ctx.Event(), ctx.Queue()
    process = ctx.Process(
        target=_blocked_worker, args=(path, selection_id, started, release, queue)
    )
    process.start()
    try:
        assert started.wait(15)
        with pytest.raises(RuntimeError, match="already running"):
            run_deep(db, selection_id, learner=LEARNER, options=options())
        config = PipelineConfig(learner=LEARNER, max_games=1, network_retries=0, network_sleep=0)
        response = sync_result(
            db,
            config,
            None,
            httpx.MockTransport(lambda request: httpx.Response(200, text="")),
            None,
            retry_only=True,
        )
        assert response is not None and response["status"] in {"complete", "partial"}
        assert db.connection.execute("SELECT COUNT(*) FROM sync_progress").fetchone()[0] == 1
        assert (
            db.connection.execute("SELECT retry_until FROM pipeline_health WHERE id=1").fetchone()[
                0
            ]
            is None
        )
        assert process.is_alive()
        release.set()
        result = queue.get(timeout=20)
        process.join(20)
        assert process.exitcode == 0 and result["processed"][0]["status"] == "complete"
    finally:
        release.set()
        if process.is_alive():
            process.terminate()
            process.join(10)


def test_process_crash_recovers_claim_without_duplicate_result(tmp_path, monkeypatch):
    import multiprocessing

    path = tmp_path / "crash.sqlite"
    db, selection_id = prepare_selected(path, monkeypatch, per_game=1)
    before = db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
    ctx = multiprocessing.get_context("spawn")
    started, release, queue = ctx.Event(), ctx.Event(), ctx.Queue()
    process = ctx.Process(
        target=_blocked_worker, args=(path, selection_id, started, release, queue)
    )
    process.start()
    try:
        assert started.wait(15)
        process.terminate()
        process.join(10)
        assert not process.is_alive()
        assert (
            db.connection.execute("SELECT status FROM deep_analysis_jobs").fetchone()[0]
            == "running"
        )
        use_engine(monkeypatch, DeepEngine(db))
        result = run_deep(db, selection_id, learner=LEARNER, options=options())
        assert result["processed"][0]["status"] == "complete"
        assert [
            row[0]
            for row in db.connection.execute(
                "SELECT status FROM deep_analysis_attempts ORDER BY attempt_number"
            )
        ] == ["interrupted", "complete"]
        assert (
            db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == before + 1
        )
    finally:
        if process.is_alive():
            process.terminate()
            process.join(10)


def test_selection_change_during_engine_work_discards_result(tmp_path, monkeypatch):
    import multiprocessing

    path = tmp_path / "stale.sqlite"
    db, selection_id = prepare_selected(path, monkeypatch, per_game=1)
    before = db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
    ctx = multiprocessing.get_context("spawn")
    started, release, queue = ctx.Event(), ctx.Event(), ctx.Queue()
    process = ctx.Process(
        target=_blocked_worker, args=(path, selection_id, started, release, queue)
    )
    process.start()
    try:
        assert started.wait(15)
        db.connection.execute(
            "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role='best'"
        )
        db.connection.commit()
        release.set()
        result = queue.get(timeout=20)
        process.join(20)
        assert process.exitcode == 0 and result["processed"][0]["status"] == "stale"
        assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == before
        assert (
            db.connection.execute("SELECT COUNT(*) FROM deep_analysis_alternatives").fetchone()[0]
            == 0
        )
    finally:
        release.set()
        if process.is_alive():
            process.terminate()
            process.join(10)


def test_result_write_failure_rolls_back_partial_run(tmp_path, monkeypatch):
    db, selection_id = prepare_selected(tmp_path / "rollback.sqlite", monkeypatch, per_game=1)
    before = db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
    db.connection.execute("""CREATE TRIGGER reject_deep BEFORE INSERT ON deep_analysis_alternatives
        BEGIN SELECT RAISE(ABORT,'synthetic failure'); END""")
    db.connection.commit()
    use_engine(monkeypatch, DeepEngine(db))
    report = run_deep(db, selection_id, learner=LEARNER, options=options())
    assert report["processed"][0]["status"] == "insufficient"
    assert report["processed"][0]["detail"] == "processing_failed"
    assert db.connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0] == before
    assert (
        db.connection.execute("SELECT COUNT(*) FROM deep_analysis_alternatives").fetchone()[0] == 0
    )
    assert (
        db.connection.execute("SELECT analysis_run_id FROM deep_analysis_attempts").fetchone()[0]
        is None
    )


def test_forced_move_limits_multipv_to_legal_alternatives(tmp_path, monkeypatch):
    import chess.pgn

    from chess_coach.ingest import ingest_pgn
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from tests.test_deep_selection import Engine

    db = Database(tmp_path / "forced.sqlite")
    db.initialize()
    board = chess.Board("7k/6R1/8/5K2/8/8/8/8 b - - 0 1")
    assert board.is_valid() and board.legal_moves.count() == 1
    game = chess.pgn.Game()
    game.setup(board)
    game.headers["White"] = "fixture_opponent"
    game.headers["Black"] = LEARNER
    game.headers["Result"] = "*"
    game.add_variation(board.parse_uci("h8g7"))
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    selected = select_deep(db, [1], learner=LEARNER, per_game=1, total=1)
    selection_id = selected["games"][0]["selection_id"]
    engine = DeepEngine(db)
    use_engine(monkeypatch, engine)
    report = run_deep(db, selection_id, learner=LEARNER, options=options())
    assert report["processed"][0]["status"] in {"complete", "unstable"}
    assert engine.calls[0][2] == 1
    item = show_selection(db, 1, LEARNER)["items"][0]
    deep = inspect_decision(db, item["position_id"], learner=LEARNER)["deep"]
    assert len(deep["result"]["alternatives"]) == 1


@pytest.mark.skipif(
    not __import__("pathlib").Path("/usr/games/stockfish").is_file(),
    reason="Stockfish not installed",
)
def test_real_stockfish_deep_smoke(tmp_path, monkeypatch):
    real = chess.engine.SimpleEngine.popen_uci
    db, selection_id = prepare_selected(tmp_path / "stockfish.sqlite", monkeypatch, per_game=1)
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", real)
    report = run_deep(
        db,
        selection_id,
        learner=LEARNER,
        options=options(engine_path="/usr/games/stockfish", nodes=3000, seconds=1.0, min_depth=1),
    )
    assert len(report["processed"]) == 1
    assert report["processed"][0]["status"] in {"complete", "insufficient"}
    item = show_selection(db, 1, LEARNER)["items"][0]
    deep = inspect_decision(db, item["position_id"], learner=LEARNER)["deep"]
    assert deep["result"] is not None and deep["result"]["best_work"]["nodes"] > 0


def test_changed_configuration_and_reactivation_preserve_history(tmp_path, monkeypatch):
    db, selection_id = prepare_selected(tmp_path / "configs.sqlite", monkeypatch, per_game=1)
    use_engine(monkeypatch, DeepEngine(db))
    original = run_deep(db, selection_id, learner=LEARNER, options=options())
    original_job = original["processed"][0]["job_id"]
    use_engine(monkeypatch, DeepEngine(db))
    updated = run_deep(db, selection_id, learner=LEARNER, options=options(nodes=2000))
    assert updated["processed"][0]["job_id"] != original_job
    assert db.connection.execute("SELECT COUNT(*) FROM deep_analysis_attempts").fetchone()[0] == 2
    use_engine(monkeypatch, DeepEngine(db))
    restored = run_deep(db, selection_id, learner=LEARNER, options=options())
    assert restored["processed"] == []
    assert (
        db.connection.execute("SELECT job_id FROM deep_analysis_current").fetchone()[0]
        == original_job
    )
    assert db.connection.execute("SELECT COUNT(*) FROM deep_analysis_attempts").fetchone()[0] == 2


def test_unverified_external_network_makes_stability_incomparable(tmp_path, monkeypatch):
    from types import SimpleNamespace

    db = setup_game(tmp_path / "network.sqlite", monkeypatch)
    row = db.connection.execute("SELECT id,config_json FROM analysis_runs").fetchone()
    config = json.loads(row["config_json"])
    config["nnue_options"] = {"EvalFile": "synthetic.nnue"}
    db.connection.execute(
        "UPDATE analysis_runs SET config_json=? WHERE id=?", (json.dumps(config), row["id"])
    )
    db.connection.commit()
    selected = select_deep(db, [1], learner=LEARNER, per_game=1, total=1)
    selection_id = selected["games"][0]["selection_id"]
    engine = DeepEngine(db, score=500)
    engine.options = {"EvalFile": SimpleNamespace(default="synthetic.nnue")}
    use_engine(monkeypatch, engine)
    result = run_deep(db, selection_id, learner=LEARNER, options=options())
    assert result["processed"][0]["status"] == "complete"
    assert result["processed"][0]["comparison"] == "incomparable"


def test_missing_stored_alternative_downgrades_displayed_result(tmp_path, monkeypatch):
    db, selection_id = prepare_selected(tmp_path / "missing-alt.sqlite", monkeypatch, per_game=1)
    use_engine(monkeypatch, DeepEngine(db))
    result = run_deep(db, selection_id, learner=LEARNER, options=options())
    assert result["processed"][0]["status"] == "complete"
    item = show_selection(db, 1, LEARNER)["items"][0]
    db.connection.execute("DELETE FROM deep_analysis_alternatives WHERE rank=3")
    db.connection.commit()
    shown = inspect_decision(db, item["position_id"], learner=LEARNER)["deep"]
    assert shown["status"] == "insufficient"
    assert shown["detail"] == "stored_result_incomplete" and shown["comparison"] == "unknown"
    assert (
        db.connection.execute("SELECT status FROM deep_analysis_jobs").fetchone()[0] == "complete"
    )
