"""Atomic revalidation and immutable event controls for owned fork defense."""

import sqlite3

import pytest

from chess_coach.objective_verify import compute
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import submit
from tests.test_fork_defense_pipeline import LEARNER
from tests.test_objective_fork_defense import begin, fixture


def test_duplicate_worker_call_keeps_one_immutable_result(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path / "duplicate.sqlite", monkeypatch)
    begin(db, evidence)
    original = submit(db, "fork-defense", LEARNER, event_id="answer", move="a1b1")
    assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    assert process(db, LEARNER)["processed"] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM objective_results").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute("UPDATE objective_results SET result_json='{}'")
    db.connection.rollback()
    assert submit(db, "fork-defense", LEARNER, event_id="answer", move="a1b1") == original
    db.close()


def test_concurrent_workers_publish_one_immutable_result(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from chess_coach.db import Database

    path = tmp_path / "concurrent.sqlite"
    db, evidence = fixture(path, monkeypatch)
    begin(db, evidence)
    submit(db, "fork-defense", LEARNER, event_id="answer", move="a1b1")
    db.close()
    barrier = Barrier(2)

    def verify_after_barrier(db, request, clock, *, seconds):
        barrier.wait(timeout=5)
        return compute(db, request, clock, seconds=seconds)

    def work(_):
        connection = Database(path)
        try:
            return process(connection, LEARNER, verifier=verify_after_barrier)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(work, range(2)))
    assert all(result["outcomes"] == {"correct": 1} for result in results)
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM objective_results").fetchone()[0] == 1
    db.close()
