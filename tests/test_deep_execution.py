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
    comparison(db, LEARNER, context, board, choices)
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
