"""Bounded deep work remains separate, resumable and provenance-aware."""

import sys
from typing import Any

import chess
import chess.engine
import pytest

from chess_coach.decision_inspection import inspect_decision
from chess_coach.deep_execution_config import DeepOptions
from chess_coach.deep_execution_worker import run_deep
from chess_coach.deep_selection import select_deep
from chess_coach.deep_selection_views import show_selection
from tests.test_deep_selection import LEARNER, setup_game


class DeepEngine:
    def __init__(self, db=None, *, score=20, mode="normal", name="Synthetic", include_root=None):
        self.id = {"name": name}
        self.options = {}
        self.db = db
        self.score = score
        self.mode = mode
        self.include_root = include_root
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
        if root_moves is None and self.include_root:
            played = board.parse_uci(self.include_root)
            choices = [played, *(move for move in board.legal_moves if move != played)][:multipv]
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
    played_move = inspect_decision(db, first["position_id"], learner=LEARNER)["played_move"]
    engine = DeepEngine(db, include_root=played_move)
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
    # Compare two roots only when they belong to this exact current MultiPV search.
    import json

    from chess_coach.decision_history import decision_board
    from chess_coach.opening_decision_analysis import comparison

    position = db.connection.execute(
        "SELECT * FROM positions WHERE id=?", (first["position_id"],)
    ).fetchone()
    board = decision_board(db, position)
    alternatives = deep["result"]["alternatives"]
    other_root = next(
        item["line"]["root_move"]
        for item in alternatives
        if item["line"]["root_move"] != played_move
    )
    choices = [{"uci": other_root}]
    context = {"position_id": first["position_id"], "played_move": played_move}
    summary = comparison(db, LEARNER, context, board, choices)
    assert summary["status"] == "available" and choices[0]["analysis"]["depth"] == 5
    row = db.connection.execute(
        "SELECT attempt_id,rank,line_json FROM deep_analysis_alternatives WHERE json_extract(line_json, '$.root_move')=?",
        (other_root,),
    ).fetchone()
    altered = json.loads(row["line_json"])
    altered["depth"] = 6
    db.connection.execute(
        "UPDATE deep_analysis_alternatives SET line_json=? WHERE attempt_id=? AND rank=?",
        (json.dumps(altered), row["attempt_id"], row["rank"]),
    )
    db.connection.commit()
    choices = [{"uci": other_root}]
    unavailable = comparison(db, LEARNER, context, board, choices)
    assert unavailable["status"] == "no catalog alternative has a qualified same-search comparison"
    assert "analysis" not in choices[0]
    db.connection.execute(
        "UPDATE deep_analysis_alternatives SET line_json=? WHERE attempt_id=? AND rank=?",
        (row["line_json"], row["attempt_id"], row["rank"]),
    )
    db.connection.commit()
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
    engine.include_root = None
    again = run_deep(db, selection_id, learner=LEARNER, options=options(max_jobs=3))
    assert len(again["processed"]) == 2
    assert db.connection.execute("SELECT COUNT(*) FROM deep_analysis_attempts").fetchone()[0] == 3
    _automatic_lane_workflow(tmp_path, monkeypatch)


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


def _automatic_lane_workflow(tmp_path, monkeypatch):
    import json
    from dataclasses import replace

    from chess_coach import pipeline_deep_lane_attempt as attempts
    from chess_coach.db import Database
    from chess_coach.deep_execution_queue import prepare_jobs
    from chess_coach.ingest import ingest_pgn
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_deep import process_deep
    from chess_coach.pipeline_deep_config import deep_options
    from chess_coach.pipeline_deep_game_finish import finished
    from chess_coach.pipeline_deep_lane_state import load, save
    from chess_coach.pipeline_deep_recent import next_game
    from chess_coach.pipeline_deep_work import execute
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from tests.test_deep_selection import PGN, Engine

    path = tmp_path / "automatic.sqlite"
    db = setup_game(path, monkeypatch)
    ingest_pgn(
        db,
        PGN.replace('Event "Synthetic"', 'Event "Second"').replace(
            'UTCTime "00:00:00"', 'UTCTime "00:00:01"'
        ),
    )
    config = PipelineConfig(
        learner=LEARNER,
        engine_path=sys.executable,
        nodes=100,
        deep_enabled=True,
        deep_max_scan=1,
        deep_max_games=1,
        deep_per_game=3,
        deep_max_jobs=1,
        deep_nodes=1000,
        deep_seconds=0.5,
        deep_multipv=3,
        hash_mb=4,
    )
    use_engine(monkeypatch, DeepEngine(db))
    first = process_deep(db, config)
    assert first["lanes"]["archive"] == 1 and first["processed"] == 1
    assert load(db, LEARNER)["archive"]["id"] == 1

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    use_engine(monkeypatch, DeepEngine(db))
    second = process_deep(db, config)
    assert second["lanes"]["recent"] == 1 and second["processed"] == 1
    assert load(db, LEARNER)["recent"]["id"] == 2
    db.close()
    db = Database(path)
    use_engine(monkeypatch, DeepEngine(db))
    reports = [process_deep(db, config) for _ in range(8)]
    assert all(
        r["examined"] <= 1 and r["processed"] <= 1 and r["selected_games"] <= 1 for r in reports
    )
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM deep_analysis_jobs WHERE status IN ('complete','unstable')"
        ).fetchone()[0]
        == 6
    )
    before = db.connection.total_changes
    select_deep(db, [1], learner=LEARNER, per_game=3, total=3)
    assert db.connection.total_changes == before
    selection_id = select_deep(db, [1], learner=LEARNER, per_game=3, total=3)["games"][0][
        "selection_id"
    ]
    recorded = json.loads(
        db.connection.execute(
            "SELECT config_json FROM deep_analysis_jobs WHERE selection_id=? LIMIT 1",
            (selection_id,),
        ).fetchone()[0]
    )
    before = db.connection.total_changes
    prepare_jobs(db, selection_id, LEARNER, recorded, False)
    assert db.connection.total_changes == before

    # An archive sweep never wraps and repeats a game in the same invocation.
    calls = []
    original = attempts.process_game

    def count_game(db, game_id, config, report, *, deadline=None):
        calls.append(game_id)
        return original(db, game_id, config, report, deadline=deadline)

    state = load(db, LEARNER)
    state.update(next_recent=False, archive=None, recent=None, after=None)
    save(db, LEARNER, state)
    monkeypatch.setattr(attempts, "process_game", count_game)
    process_deep(db, replace(config, deep_max_scan=20, deep_max_games=20, deep_max_jobs=20))
    assert len(calls) == len(set(calls)) == 2

    # Unavailable recent sources finish one current-window sweep, then yield to archive.
    def no_source(db, game_id, config, report, *, deadline=None):
        report["unavailable"] += 1
        return True

    state = load(db, LEARNER)
    state.update(next_recent=True, archive=None, recent=None, after=None)
    save(db, LEARNER, state)
    monkeypatch.setattr(attempts, "process_game", no_source)
    sweep = process_deep(db, replace(config, deep_max_scan=20, deep_max_games=20, deep_max_jobs=20))
    assert sweep["lanes"] == {"recent": 2, "archive": 2}
    assert sweep["unavailable"] == 2 and sweep["examined"] == 4
    monkeypatch.setattr(attempts, "process_game", original)

    # An exhausted search budget produces an automatically retried insufficient job.
    import time

    from chess_coach import deep_execution_search

    deadline_db = setup_game(tmp_path / "deadline.sqlite", monkeypatch)
    deadline_selection = select_deep(deadline_db, [1], learner=LEARNER, per_game=1, total=1)[
        "games"
    ][0]["selection_id"]
    use_engine(monkeypatch, DeepEngine(deadline_db))
    search_timeout = deep_execution_search.search_timeout
    monkeypatch.setattr(deep_execution_search, "search_timeout", lambda *_: None)
    timed_result = run_deep(
        deadline_db,
        deadline_selection,
        learner=LEARNER,
        options=deep_options(config),
        deadline=time.monotonic() + 30,
    )
    assert timed_result["processed"][0]["detail"] == "worker_deadline"
    detail = {}
    assert not finished(timed_result, detail) and detail["detail"] == "worker_deadline"
    monkeypatch.setattr(deep_execution_search, "search_timeout", search_timeout)
    use_engine(monkeypatch, DeepEngine(deadline_db))
    recovered = execute(deadline_db, 1, deadline_selection, config, 1)
    assert recovered["processed"][0]["status"] in {"complete", "unstable"}
    assert (
        deadline_db.connection.execute("SELECT COUNT(*) FROM deep_analysis_attempts").fetchone()[0]
        == 2
    )
    deadline_db.close()
    use_engine(monkeypatch, DeepEngine(db))

    # A saved failure gets one retry, then yields to the next candidate.
    original = attempts.process_game

    def unavailable(db, game_id, config, report, *, deadline=None):
        if game_id == 2:
            report["detail"] = "selection_unavailable"
            return False
        return original(db, game_id, config, report, deadline=deadline)

    state = load(db, LEARNER)
    state.update(next_recent=True, after=None, recent=None)
    save(db, LEARNER, state)
    monkeypatch.setattr(attempts, "process_game", unavailable)
    process_deep(db, config)
    assert load(db, LEARNER)["recent"]["attempts"] == 1
    db.close()
    db = Database(path)
    use_engine(monkeypatch, DeepEngine(db))
    process_deep(db, config)
    failed = process_deep(db, config)
    assert failed["skipped_failures"] == 1 and load(db, LEARNER)["recent"] is None

    # Deadline stalls retain the checkpoint once, then yield without deleting jobs.
    def interrupted(db, game_id, config, report, *, deadline=None):
        report["detail"] = "worker_deadline"
        return False

    state = load(db, LEARNER)
    state.update(next_recent=True, after=None, recent=None)
    save(db, LEARNER, state)
    monkeypatch.setattr(attempts, "process_game", interrupted)
    timed = process_deep(db, config)
    assert timed["capped"] and load(db, LEARNER)["recent"]["attempts"] == 1
    db.close()
    db = Database(path)
    state = load(db, LEARNER)
    state["next_recent"] = True
    save(db, LEARNER, state)
    timed_again = process_deep(db, config)
    assert timed_again["skipped_failures"] == 1 and load(db, LEARNER)["recent"] is None
    state = load(db, LEARNER)
    state["next_recent"] = True
    save(db, LEARNER, state)
    monkeypatch.setattr(attempts, "process_game", original)
    use_engine(monkeypatch, DeepEngine(db))
    later = process_deep(db, config)
    assert later["lanes"]["recent"] == 1 and later["selected_games"] == 1

    # Changing selection policy discards the old pending archive before resetting its cursor.
    state = load(db, LEARNER)
    state.update(next_recent=False, archive={"id": 2, "started": None, "attempts": 0})
    save(db, LEARNER, state)
    changed = process_deep(db, replace(config, deep_per_game=2))
    assert changed["lanes"]["archive"] == 1
    assert load(db, LEARNER)["archive"]["id"] == 1

    # Displaced anchors restart within the current ten, even when an old game was pending.
    for index in range(3, 15):
        ingest_pgn(
            db,
            PGN.replace('Event "Synthetic"', f'Event "Arrival {index}"').replace(
                'UTCTime "00:00:00"', f'UTCTime "00:00:{index:02d}"'
            ),
        )
    state = load(db, LEARNER)
    state.update(after=["2026-01-01T00:00:00+00:00", 1])
    item, _, _ = next_game(db, config, state)
    assert item["id"] == 14
    state.update(per_game=3, next_recent=True, archive=None, recent=None, after=None)
    save(db, LEARNER, state)
    monkeypatch.setattr(attempts, "process_game", no_source)
    window = process_deep(
        db, replace(config, deep_max_scan=20, deep_max_games=20, deep_max_jobs=20)
    )
    assert window["lanes"] == {"recent": 10, "archive": 10}
    assert window["unavailable"] == 14

    # A wrapped pending archive game resumes by its own ID, even after a new import.
    from chess_coach.pipeline_deep_cursor import advance
    from chess_coach.pipeline_deep_cursor_state import _cursor

    key, _, version = _cursor(db, config)
    advance(db, key, version, 14)
    state = load(db, LEARNER)
    state.update(next_recent=False, archive={"id": 1, "started": None, "attempts": 0})
    save(db, LEARNER, state)
    ingest_pgn(db, PGN.replace('Event "Synthetic"', 'Event "New Arrival"'))
    observed = []

    def track(db, game_id, config, report, *, deadline=None):
        observed.append(game_id)
        return True

    monkeypatch.setattr(attempts, "process_game", track)
    wrapped = process_deep(
        db, replace(config, deep_max_scan=3, deep_max_games=20, deep_max_jobs=20)
    )
    assert wrapped["lanes"]["archive"] == 3 and observed == [1, 2, 3]
    assert _cursor(db, config)[1] == 3

    # A deadline after successful work resets the stall count.
    def progress_then_deadline(db, game_id, config, report, *, deadline=None):
        report["processed"] += 1
        report["advanced"] += 1
        report["detail"] = "worker_deadline"
        return False

    state = load(db, LEARNER)
    state.update(next_recent=False, archive={"id": 4, "started": None, "attempts": 1})
    save(db, LEARNER, state)
    monkeypatch.setattr(attempts, "process_game", progress_then_deadline)
    progress = process_deep(db, config)
    assert progress["capped"] and load(db, LEARNER)["archive"]["attempts"] == 0
    db.close()
