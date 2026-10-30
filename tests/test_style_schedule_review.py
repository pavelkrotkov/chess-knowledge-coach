"""Independent rotation and purpose-preflight regression coverage."""

import pytest

from chess_coach.db import Database
from chess_coach.style_schedule_budget import history_budget
from chess_coach.style_schedule_store import create_cycle, update_slot
from tests.test_deep_selection import LEARNER


def synthetic_pool(db, per_game):
    for game_id in range(1, 11):
        db.connection.execute(
            "INSERT INTO games(id,pgn,white,black,result) VALUES(?,?,?,?,?)",
            (game_id, "synthetic", "fixture_learner", "fixture_opponent", "*"),
        )
        for number in range(1, per_game + 1):
            db.connection.execute(
                "INSERT INTO positions(id,game_id,ply,fen,san,uci) VALUES(?,?,?,?,?,?)",
                (game_id * 1000 + number, game_id, number, "synthetic", "a3", "a2a3"),
            )
    db.connection.commit()


@pytest.mark.parametrize(("kind", "per_game"), [("control", 100), ("target", 2)])
def test_independent_rotation_covers_each_candidate_under_one_game_scan(
    monkeypatch, kind, per_game
):
    import chess_coach.style_schedule_candidates as candidates

    db = Database(":memory:")
    db.initialize()
    synthetic_pool(db, per_game)
    games = [({"id": game_id}, "white") for game_id in range(1, 11)]
    monkeypatch.setattr(
        candidates, "recent_games", lambda *_args, **_kwargs: (games, {"game_limit_reached": False})
    )

    def one_game_scan(_db, _games, sequence):
        game_id = sequence % 10 + 1
        items = [
            {
                "game_id": game_id,
                "position_id": game_id * 1000 + number,
                "in_check": kind == "target",
                "status": "unknown" if number == 1 else "ready",
                "detail": "synthetic_skipped" if number == 1 else "eligible",
            }
            for number in range(1, per_game + 1)
        ]
        return items, 0, 0, True, 1

    monkeypatch.setattr(candidates, "read_games", one_game_scan)
    visited = {game_id: set() for game_id in range(1, 11)}
    for sequence in range(10 * per_game):
        with history_budget():
            cycle = create_cycle(db, LEARNER)
        slot = db.connection.execute(
            "SELECT * FROM style_schedule_slots WHERE cycle_id=? AND kind=?", (cycle, kind)
        ).fetchone()
        visited[slot["game_id"]].add(slot["position_id"])
        if slot["status"] == "ready":
            outcome = "insufficient" if sequence % 2 else "interrupted"
            update_slot(db, slot["id"], outcome, "synthetic_attempt")
    assert all(len(positions) == per_game for positions in visited.values())
    counts = db.connection.execute(
        "SELECT next_index FROM style_schedule_rotation WHERE kind=? ORDER BY game_id", (kind,)
    ).fetchall()
    assert [row[0] for row in counts] == [per_game] * 10


def test_preflight_schema_failure_does_not_suppress_other_worker_families(monkeypatch):
    import chess_coach.pipeline as pipeline
    import chess_coach.pipeline_deep_arbitration as arbitration
    from chess_coach.pipeline_config import PipelineConfig

    db = Database(":memory:")
    db.initialize()
    db.connection.execute("DROP INDEX idx_style_schedule_owner")
    db.connection.commit()
    calls = []

    def normal(*_args, **_kwargs):
        calls.append("normal")
        return {"status": "complete", "processed": []}

    def family(name):
        def call(*_args, **_kwargs):
            calls.append(name)
            return {"status": "complete"}

        return call

    monkeypatch.setattr(arbitration, "process_deep", normal)
    monkeypatch.setattr(
        arbitration, "process_schedule", lambda *_a, **_k: pytest.fail("purpose ran")
    )
    monkeypatch.setattr(pipeline, "sync_result", lambda *_a: {"status": "complete"})
    monkeypatch.setattr(pipeline, "engine_identity", lambda *_a: "synthetic")
    monkeypatch.setattr(
        pipeline, "pending_games", lambda *_a: ([], {"has_more": False}, ("key", 0, "scan"))
    )
    monkeypatch.setattr(pipeline, "save_cursor", lambda *_a: None)
    monkeypatch.setattr(pipeline, "scan_input", lambda *_a: "scan")
    monkeypatch.setattr(pipeline, "process_material", family("material"))
    monkeypatch.setattr(pipeline, "process_forks", family("forks"))
    monkeypatch.setattr(pipeline, "process_defenses", family("defenses"))
    monkeypatch.setattr(pipeline, "worker_report", lambda *_a: {"status": "complete"})
    result = pipeline._run_pipeline(db, PipelineConfig(learner=LEARNER), None, None, None)
    assert calls == ["normal", "material", "forks", "defenses"]
    assert result["status"] == "partial"
    assert result["purpose_schedule"] == {
        "status": "partial",
        "detail": "purpose_schedule_unavailable",
    }


def test_allocation_and_rotation_advance_roll_back_together():
    import sqlite3

    from chess_coach.ingest import ingest_pgn
    from tests.test_style_schedule import CHECK, CONTROL

    db = Database(":memory:")
    db.initialize()
    ingest_pgn(db, CHECK)
    ingest_pgn(db, CONTROL)
    db.connection.execute(
        """CREATE TRIGGER reject_rotation BEFORE INSERT ON style_schedule_rotation
        BEGIN SELECT RAISE(ABORT,'synthetic failure'); END"""
    )
    db.connection.commit()
    with history_budget(), pytest.raises(sqlite3.IntegrityError, match="synthetic failure"):
        create_cycle(db, LEARNER)
    for table in ("style_schedule_cycles", "style_schedule_slots", "style_schedule_rotation"):
        assert db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
