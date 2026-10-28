from __future__ import annotations

import json
from datetime import UTC, datetime

import chess
import pytest

from chess_coach import fact_run_apply
from chess_coach.db import SCHEMA, Database
from chess_coach.fact_runs import record_fact_run, record_fact_run_in_transaction
from chess_coach.fact_schema import RUN_TABLE

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


def test_same_input_and_version_cannot_silently_change_output():
    db = database()
    first = produce(db)
    before = snapshot(db)
    with pytest.raises(ValueError, match="output changed"):
        produce(db, facts=[{"fact_type": "fork", "payload": {"attacker": "d4"}}])
    assert snapshot(db) == before
    assert produce(db)["run_id"] == first["run_id"]


def test_same_version_with_new_input_creates_linked_run():
    db = database()
    first = produce(db)
    new = produce(db, inputs={"mode": "different"})
    assert new["run_id"] != first["run_id"]
    assert (
        db.connection.execute(
            "SELECT supersedes_run_id FROM detector_runs WHERE id = ?", (new["run_id"],)
        ).fetchone()[0]
        == first["run_id"]
    )
    assert produce(db)["status"] == "superseded"


@pytest.mark.parametrize(
    "invalid",
    [
        [{"fact_type": "", "payload": {}}],
        [{"fact_type": "fork", "payload": ["not an object"]}],
        [{"fact_type": "fork", "payload": {"bad": float("nan")}}],
        [FACTS[0], FACTS[0]],
        [{"unexpected": "value"}],
    ],
)
def test_invalid_batch_leaves_active_run_unchanged(invalid):
    db = database()
    produce(db)
    before = snapshot(db)
    with pytest.raises(ValueError):
        produce(db, version="v2", facts=invalid)
    assert snapshot(db) == before
    assert not db.connection.in_transaction


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


def test_callers_can_compose_without_implicit_commit_or_rollback():
    db = database()
    db.connection.execute("BEGIN IMMEDIATE")
    result = record_fact_run_in_transaction(
        db, position_id=1, producer="motif", detector_version="v1", input_data={}, facts=FACTS
    )
    assert result["fact_ids"]
    assert db.connection.in_transaction
    with pytest.raises(RuntimeError, match="existing transaction"):
        produce(db)
    assert db.connection.in_transaction
    db.connection.rollback()
    assert db.connection.execute("SELECT COUNT(*) FROM detector_runs").fetchone()[0] == 0
    with pytest.raises(RuntimeError, match="requires a transaction"):
        record_fact_run_in_transaction(
            db, position_id=1, producer="motif", detector_version="v1", input_data={}, facts=FACTS
        )


def test_replay_rejects_missing_or_modified_stored_facts():
    db = database()
    result = produce(db)
    db.connection.execute(
        "UPDATE detector_facts SET payload_json = '{}' WHERE id = ?", (result["fact_ids"][0],)
    )
    db.connection.commit()
    with pytest.raises(ValueError, match="stored facts"):
        produce(db)


def test_v5_legacy_fact_and_review_migrate_without_fabricated_lineage():
    from chess_coach.puzzle_session_schema import add_puzzle_sessions

    legacy = SCHEMA.replace(RUN_TABLE, "").replace(
        "    payload_json TEXT NOT NULL,\n    run_id INTEGER REFERENCES detector_runs(id),\n"
        "    fact_key TEXT,\n    produced_at TEXT\n",
        "    payload_json TEXT NOT NULL\n",
    )
    db = Database(":memory:")
    db.connection.executescript(legacy)
    add_puzzle_sessions(db.connection)
    db.connection.execute(
        "INSERT INTO games (pgn, white, black, result) VALUES ('raw', 'A', 'B', '*')"
    )
    db.connection.execute(
        "INSERT INTO positions (game_id, ply, fen, san, uci) VALUES (1, 1, 'fen', 'e4', 'e2e4')"
    )
    db.connection.execute(
        "INSERT INTO detector_facts (position_id, detector_version, fact_type, payload_json) "
        "VALUES (1, 'old', 'fork', '{}')"
    )
    db.connection.execute(
        "INSERT INTO evidence_mappings (position_id, skill, operation, outcome, confidence, source_facts_json, human_validated) "
        "VALUES (1, 'fork', 'execute', 'success', 1, '[{\"id\": 1}]', 1)"
    )
    db.connection.execute("PRAGMA user_version = 5")
    db.connection.commit()
    old_evidence = tuple(db.connection.execute("SELECT * FROM evidence_mappings").fetchone())
    db.initialize()
    db.initialize()
    fact = db.connection.execute(
        "SELECT id, run_id, fact_key, produced_at FROM detector_facts"
    ).fetchone()
    assert tuple(fact) == (1, None, None, None)
    assert (
        tuple(db.connection.execute("SELECT * FROM evidence_mappings").fetchone())[
            : len(old_evidence)
        ]
        == old_evidence
    )
    assert db.connection.execute("SELECT COUNT(*) FROM detector_runs").fetchone()[0] == 0
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 13
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []
    new = produce(db)
    assert new["fact_ids"]
    assert (
        db.connection.execute("SELECT run_id FROM detector_facts WHERE id = 1").fetchone()[0]
        is None
    )
    assert (
        tuple(db.connection.execute("SELECT * FROM evidence_mappings").fetchone())[
            : len(old_evidence)
        ]
        == old_evidence
    )


def test_failed_v6_migration_rolls_back_schema_and_version(monkeypatch):
    from chess_coach import db_recent

    legacy = SCHEMA.replace(RUN_TABLE, "").replace(
        "    payload_json TEXT NOT NULL,\n    run_id INTEGER REFERENCES detector_runs(id),\n"
        "    fact_key TEXT,\n    produced_at TEXT\n",
        "    payload_json TEXT NOT NULL\n",
    )
    db = Database(":memory:")
    db.connection.executescript(legacy)
    db.connection.execute("PRAGMA user_version = 5")
    db.connection.commit()
    original = db_recent.add_fact_lineage

    def fail_after_schema(connection):
        original(connection)
        raise RuntimeError("injected schema failure")

    monkeypatch.setattr(db_recent, "add_fact_lineage", fail_after_schema)
    with pytest.raises(RuntimeError, match="injected schema failure"):
        db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 5
    assert (
        db.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'detector_runs'"
        ).fetchone()
        is None
    )
    columns = {row[1] for row in db.connection.execute("PRAGMA table_info(detector_facts)")}
    assert {"run_id", "fact_key", "produced_at"}.isdisjoint(columns)
    assert db.connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_current_motif_detector_can_supply_the_fact_run_without_creating_evidence():
    from chess_coach.motifs import detect_motifs

    db = database()
    board = chess.Board("4k3/8/8/8/8/2N5/8/4K3 w - - 0 1")
    board.set_piece_at(chess.E4, chess.Piece(chess.KNIGHT, chess.WHITE))
    board.set_piece_at(chess.C5, chess.Piece(chess.ROOK, chess.BLACK))
    board.set_piece_at(chess.F6, chess.Piece(chess.BISHOP, chess.BLACK))
    db.connection.execute("UPDATE positions SET fen = ? WHERE id = 1", (board.fen(),))
    db.connection.commit()
    detected = detect_motifs(board, detector_version="v1")
    facts = [{"fact_type": item["motif"], "payload": item} for item in detected]
    assert facts
    run = produce(db, inputs={"fen": board.fen()}, facts=facts)
    stored = db.connection.execute(
        "SELECT fact_type, payload_json FROM detector_facts WHERE run_id = ?", (run["run_id"],)
    ).fetchall()
    assert {
        (row["fact_type"], json.loads(row["payload_json"])["position_fen"]) for row in stored
    } == {(item["motif"], board.fen()) for item in detected}
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0
