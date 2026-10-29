"""Snapshot-scoped material preview history reuse."""

import sqlite3

import pytest

from chess_coach.db import Database
from chess_coach.decision_history import decision_board
from chess_coach.ingest import ingest_pgn
from chess_coach.material_context import NotLearnerDecision, context_for_position
from chess_coach.preview_snapshot import preview_history
from chess_coach.unified_own_game import list_candidates
from tests.test_material_pipeline import LEARNER
from tests.test_unified_own_game import begin, fixture

GAMES = """[Event "synthetic one"]
[White "fixture_learner"]
[Black "fixture_opponent"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 *

[Event "synthetic two"]
[White "fixture_learner"]
[Black "fixture_opponent"]
[Result "*"]

1. d4 d5 2. c4 e6 *
"""


def games_db(tmp_path):
    db = Database(tmp_path / "history.sqlite")
    db.initialize()
    ingest_pgn(db, GAMES)
    return db


def test_same_game_reuses_one_walk_and_different_games_remain_separate(tmp_path, monkeypatch):
    import chess_coach.preview_history as module

    db = games_db(tmp_path)
    positions = list(db.connection.execute("SELECT * FROM positions ORDER BY game_id, ply"))
    chosen = (positions[0], positions[2], positions[4], positions[6])
    expected = {
        row["id"]: (
            context_for_position(db, row["game_id"], row["id"], LEARNER),
            decision_board(db, row),
        )
        for row in chosen
    }
    original = module.decision_context_boards
    calls = []

    def counted(db, game_id, *, learner):
        calls.append(game_id)
        return original(db, game_id, learner=learner)

    monkeypatch.setattr(module, "decision_context_boards", counted)
    with preview_history(db, LEARNER) as history:
        history.targets(row["id"] for row in chosen)
        for row in (chosen[1], chosen[0], chosen[3], chosen[2], chosen[1]):
            context = history.context(row["game_id"], row["id"])
            board = history.board(row["game_id"], row["id"])
            old_context, old_board = expected[row["id"]]
            assert {k: v for k, v in context.items() if k != "processed_at"} == {
                k: v for k, v in old_context.items() if k != "processed_at"
            }
            assert board.fen() == old_board.fen() and board.move_stack == old_board.move_stack
        assert len(calls) == 2
        board.push(next(iter(board.legal_moves)))
        assert (
            history.board(chosen[1]["game_id"], chosen[1]["id"]).fen()
            == expected[chosen[1]["id"]][1].fen()
        )
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            db.connection.execute("UPDATE games SET event='tampered'")
    assert db.connection.execute("PRAGMA query_only").fetchone()[0] == 0
    assert not history.games and not history.wanted
    with pytest.raises(ValueError, match="snapshot is closed"):
        history.context(chosen[0]["game_id"], chosen[0]["id"])
    db.close()


def test_wrong_owner_and_later_corrupt_move_fail_closed(tmp_path):
    db = games_db(tmp_path)
    rows = list(db.connection.execute("SELECT * FROM positions WHERE game_id=1 ORDER BY ply"))
    db.connection.execute("UPDATE positions SET uci='bad' WHERE id=?", (rows[3]["id"],))
    db.connection.commit()
    with preview_history(db, LEARNER) as history:
        history.targets([row["id"] for row in rows])
        assert history.context(1, rows[0]["id"])["subject"] == LEARNER
        with pytest.raises(NotLearnerDecision):
            history.context(1, rows[1]["id"])
        with pytest.raises(ValueError):
            history.board(1, rows[3]["id"])
        assert history.context(1, rows[0]["id"])["subject"] == LEARNER
    db.close()


def test_concurrent_change_is_snapshot_scoped_and_admission_rechecks(tmp_path, monkeypatch):
    import chess_coach.unified_own_game as module

    db, _evidence = fixture(tmp_path, monkeypatch)
    db.connection.execute("PRAGMA journal_mode=WAL")
    writer = Database(tmp_path / "own.sqlite")
    original = module._inspect
    changed = False

    def inspect_with_change(db, evidence_id, subject, history):
        nonlocal changed
        if not changed:
            writer.connection.execute(
                "UPDATE decision_analysis_lines SET score_value=score_value+1 "
                "WHERE position_id=1 AND role=?",
                ("best",),
            )
            writer.connection.commit()
            changed = True
        return original(db, evidence_id, subject, history)

    monkeypatch.setattr(module, "_inspect", inspect_with_change)
    preview = list_candidates(db, LEARNER)
    assert changed and len(preview["candidates"]) == 1
    key = preview["candidates"][0]["key"]
    assert list_candidates(db, LEARNER)["candidates"] == []
    with pytest.raises(ValueError, match=r"stale|unavailable"):
        begin(db, key)
    writer.close()
    db.close()


def test_nested_snapshot_preserves_existing_transaction_and_query_only(tmp_path):
    db = games_db(tmp_path)
    db.connection.execute("UPDATE games SET event='pending' WHERE id=1")
    assert db.connection.in_transaction
    with preview_history(db, LEARNER):
        assert db.connection.execute("PRAGMA query_only").fetchone()[0] == 1
    assert db.connection.in_transaction
    assert db.connection.execute("PRAGMA query_only").fetchone()[0] == 0
    db.connection.rollback()
    db.close()


def test_populated_library_renders_multiple_games_and_rechecks_versions(tmp_path, monkeypatch):
    import io
    import sys

    import chess.pgn

    import chess_coach.preview_history as history_module
    from chess_coach.material_detector import process_decision
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.web import create_app

    db, first = fixture(tmp_path, monkeypatch)
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 "
        "WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    newer = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    assert first != newer
    original_pgn = db.connection.execute("SELECT pgn FROM games WHERE id=1").fetchone()[0]
    game = chess.pgn.read_game(io.StringIO(original_pgn))
    assert game is not None
    game.headers["Event"] = "synthetic second game"
    ingest_pgn(db, str(game))
    position = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=2 ORDER BY ply LIMIT 1"
    ).fetchone()[0]
    config = PipelineConfig(learner=LEARNER, engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 2, game_input(db, 2), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    process_decision(db, position, LEARNER)
    calls = []
    original = history_module.decision_context_boards

    def counted(db, game_id, *, learner):
        calls.append(game_id)
        return original(db, game_id, learner=learner)

    monkeypatch.setattr(history_module, "decision_context_boards", counted)
    db.close()
    app = create_app(
        db_path=tmp_path / "own.sqlite",
        subject=LEARNER,
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    for _ in range(2):
        page = client.get(
            "/library",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
        assert page.status_code == 200
        assert page.data.count(b"provisional") >= 2
        assert b"d4d5" not in page.data
    assert len(calls) == 4


def test_snapshot_restores_existing_readonly_flag_on_error(tmp_path):
    db = games_db(tmp_path)
    db.connection.execute("PRAGMA query_only=ON")
    with pytest.raises(RuntimeError, match="injected"), preview_history(db, LEARNER):
        raise RuntimeError("injected")
    assert db.connection.execute("PRAGMA query_only").fetchone()[0] == 1
    assert not db.connection.in_transaction
    db.close()


def test_history_cannot_cross_database_or_learner_scope(tmp_path, monkeypatch):
    from chess_coach.material_source import prepare

    db, _ = fixture(tmp_path, monkeypatch)
    other = Database(tmp_path / "other.sqlite")
    with preview_history(db, LEARNER) as history:
        with pytest.raises(ValueError, match="scope differs"):
            prepare(db, 1, "different", history=history)
        with pytest.raises(ValueError, match="scope differs"):
            prepare(other, 1, LEARNER, history=history)
    other.close()
    db.close()


def test_preview_in_existing_transaction_preserves_pending_changes(tmp_path, monkeypatch):
    db, _ = fixture(tmp_path, monkeypatch)
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 "
        "WHERE position_id=1 AND role=?",
        ("best",),
    )
    assert list_candidates(db, LEARNER)["candidates"] == []
    assert db.connection.in_transaction
    db.connection.rollback()
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    db.close()
