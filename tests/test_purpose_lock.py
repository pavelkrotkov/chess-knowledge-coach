"""Synthetic purpose diagnostic coverage."""

import chess
import chess.engine
import pytest

from chess_coach.purpose_worker import run
from tests.purpose_fixtures import CandidateEngine, configure, request
from tests.test_deep_selection import LEARNER, setup_game


def test_lock_excludes_other_deep_workers_and_deadline_starts_no_search(tmp_path, monkeypatch):
    from chess_coach.deep_execution_lock import deep_lock
    from chess_coach.purpose_search import search

    db = setup_game(tmp_path / "lock.sqlite", monkeypatch)
    request_id = request(db)
    engine = configure(monkeypatch, db)
    with deep_lock(db.path), pytest.raises(RuntimeError, match="already running"):
        run(db, request_id, LEARNER)
    assert not engine.calls
    result, issue = search(engine, chess.Board(), {"id": 1, "uci": "e2e4"}, 0)
    assert issue == "worker_deadline" and not engine.calls
    assert result["global_best"] == "unknown"


def test_two_purpose_workers_cannot_publish_conflicting_attempts(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from chess_coach.db import Database

    path = tmp_path / "concurrent.sqlite"
    db = setup_game(path, monkeypatch)
    request_id = request(db)
    db.close()
    entered, release = Event(), Event()

    class WaitingEngine(CandidateEngine):
        def analyse(self, board, limit, multipv, root_moves=None):
            if root_moves is None:
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("synthetic wait")
            return super().analyse(board, limit, multipv, root_moves)

    monkeypatch.setattr(
        chess.engine.SimpleEngine, "popen_uci", lambda _binary, timeout: WaitingEngine(None)
    )

    def first_worker():
        first = Database(path)
        try:
            return run(first, request_id, LEARNER)
        finally:
            first.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(first_worker)
        try:
            assert entered.wait(5)
            second = Database(path)
            try:
                with pytest.raises(RuntimeError, match="already running"):
                    run(second, request_id, LEARNER)
                assert (
                    second.connection.execute(
                        "SELECT COUNT(*) FROM purpose_analysis_attempts"
                    ).fetchone()[0]
                    == 0
                )
            finally:
                second.close()
        finally:
            release.set()
        assert future.result(timeout=10)["status"] == "complete"
    checked = Database(path)
    try:
        assert (
            checked.connection.execute("SELECT COUNT(*) FROM purpose_analysis_attempts").fetchone()[
                0
            ]
            == 1
        )
    finally:
        checked.close()
