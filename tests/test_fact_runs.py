from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from chess_coach import fact_run_apply
from chess_coach.db import Database
from chess_coach.fact_runs import record_fact_run

FACTS = [
    {"fact_type": "fork", "payload": {"attacker": "e4", "targets": ["c5", "f6"]}},
    {"fact_type": "pin", "payload": {"square": "e7"}},
]


def database() -> Database:
    db = Database(":memory:")
    db.initialize()
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('raw', 'A', 'B', '*')"
    )
    db.connection.executemany(
        "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (1, ?, ?, ?, ?)",
        [(1, "fen-one", "e4", "e2e4"), (2, "fen-two", "e5", "e7e5")],
    )
    db.connection.commit()
    return db


def produce(db: Database, *, position=1, producer="motif", version="v1", inputs=None, facts=None):
    return record_fact_run(
        db,
        position_id=position,
        producer=producer,
        detector_version=version,
        input_data={"mode": "scan"} if inputs is None else inputs,
        facts=FACTS if facts is None else facts,
    )


def snapshot(db: Database) -> tuple[list[tuple], list[tuple]]:
    return (
        [tuple(row) for row in db.connection.execute("SELECT * FROM detector_runs ORDER BY id")],
        [tuple(row) for row in db.connection.execute("SELECT * FROM detector_facts ORDER BY id")],
    )


def test_exact_replay_has_stable_ids_and_utc_provenance():
    db = database()
    first = produce(db)
    replay = produce(db, facts=list(reversed(FACTS)))
    assert replay == {**first, "replayed": True}
    assert len(first["fact_ids"]) == 2
    run = db.connection.execute(
        "SELECT * FROM detector_runs WHERE id = ?", (first["run_id"],)
    ).fetchone()
    assert (run["producer"], run["position_id"], run["detector_version"], run["status"]) == (
        "motif",
        1,
        "v1",
        "active",
    )
    assert json.loads(run["input_json"]) == {
        "position_fen": "fen-one",
        "detector_input": {"mode": "scan"},
    }
    assert datetime.fromisoformat(run["produced_at"]).utcoffset() == UTC.utcoffset(None)
    facts = db.connection.execute(
        "SELECT id, run_id, fact_key, produced_at FROM detector_facts WHERE run_id = ? ORDER BY fact_key",
        (first["run_id"],),
    ).fetchall()
    assert [row["id"] for row in facts] == first["fact_ids"]
    assert all(row["run_id"] == first["run_id"] and row["fact_key"] for row in facts)
    assert all(row["produced_at"] == run["produced_at"] for row in facts)


def test_new_versions_supersede_only_scope_and_preserve_older_fact_ids():
    db = database()
    original = produce(db)
    other_producer = produce(db, producer="independent")
    other_position = produce(db, position=2)
    new = produce(db, version="v2", facts=[])
    assert new["fact_ids"] == []
    run = db.connection.execute(
        "SELECT status, supersedes_run_id FROM detector_runs WHERE id = ?", (new["run_id"],)
    ).fetchone()
    assert tuple(run) == ("active", original["run_id"])
    old_replay = produce(db)
    assert old_replay["run_id"] == original["run_id"]
    assert old_replay["fact_ids"] == original["fact_ids"]
    assert old_replay["status"] == "superseded"
    assert old_replay["replayed"]
    active = {
        row["id"]
        for row in db.connection.execute("SELECT id FROM detector_runs WHERE status = 'active'")
    }
    assert active == {new["run_id"], other_producer["run_id"], other_position["run_id"]}
    assert db.connection.execute("SELECT COUNT(*) FROM detector_facts").fetchone()[0] == 6


def test_failure_after_partial_fact_writes_rolls_back_everything(monkeypatch):
    db = database()
    first = produce(db)
    before = snapshot(db)
    original = fact_run_apply.insert_fact
    calls = []

    def fail_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("injected failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(fact_run_apply, "insert_fact", fail_second)
    with pytest.raises(RuntimeError, match="injected"):
        produce(db, version="v2")
    assert not db.connection.in_transaction
    db.connection.execute("UPDATE games SET event = 'later' WHERE id = 1")
    db.connection.commit()
    assert snapshot(db) == before
    assert (
        db.connection.execute(
            "SELECT status FROM detector_runs WHERE id = ?", (first["run_id"],)
        ).fetchone()[0]
        == "active"
    )
