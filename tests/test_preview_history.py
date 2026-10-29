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
    source_calls = []
    import chess_coach.preview_sources as sources_module

    original_source = sources_module.source_snapshot

    def counted_source(db, game_id, learner):
        source_calls.append(game_id)
        return original_source(db, game_id, learner)

    monkeypatch.setattr(sources_module, "source_snapshot", counted_source)
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
    assert sorted(source_calls) == [1, 1, 2, 2]


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


def test_lru_eviction_rewalks_only_the_evicted_game(tmp_path, monkeypatch):
    import chess_coach.preview_history as module

    db = games_db(tmp_path)
    for number in range(3, 6):
        ingest_pgn(db, GAMES.split("\n\n[Event")[0].replace("synthetic one", f"synthetic {number}"))
    rows = list(
        db.connection.execute(
            "SELECT game_id, MIN(id) AS id FROM positions GROUP BY game_id ORDER BY game_id"
        )
    )
    assert len(rows) == 5
    calls = []
    original = module.decision_context_boards

    def counted(db, game_id, *, learner):
        calls.append(game_id)
        return original(db, game_id, learner=learner)

    monkeypatch.setattr(module, "decision_context_boards", counted)
    with preview_history(db, LEARNER) as history:
        history.targets(row["id"] for row in rows)
        for index in (0, 1, 2, 3, 0, 4, 0, 1):
            row = rows[index]
            assert history.context(row["game_id"], row["id"])["game_id"] == row["game_id"]
        assert calls == [rows[i]["game_id"] for i in (0, 1, 2, 3, 4, 1)]
    db.close()


def test_missing_target_exhausts_history_but_keeps_prior_entries(tmp_path):
    db = games_db(tmp_path)
    first = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 ORDER BY ply"
    ).fetchone()[0]
    with preview_history(db, LEARNER) as history:
        history.targets([first, 99999])
        context = history.context(1, first)
        context["subject"] = "tampered"
        for _ in range(2):
            with pytest.raises(ValueError, match="decision is not in game history"):
                history.board(1, 99999)
        assert history.context(1, first)["subject"] == LEARNER
        with pytest.raises(ValueError, match="position outside preview"):
            history.board(1, first + 1)
        db.connection.execute("PRAGMA query_only=OFF")
        with pytest.raises(ValueError, match="snapshot is not read-only"):
            history.board(1, first)
        db.connection.execute("PRAGMA query_only=ON")
    db.close()


@pytest.mark.parametrize("corruption", ["pgn", "variant", "missing_ply"])
def test_corrupt_history_excludes_candidate_and_does_not_survive_next_request(
    tmp_path, monkeypatch, corruption
):
    db, _ = fixture(tmp_path, monkeypatch)
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    db.connection.execute("SAVEPOINT corrupt")
    if corruption == "pgn":
        db.connection.execute("UPDATE games SET pgn=? WHERE id=1", ("[broken",))
    elif corruption == "variant":
        db.connection.execute("UPDATE games SET variant=? WHERE id=1", ("Chess960",))
    else:
        db.connection.execute(
            "DELETE FROM positions WHERE game_id=1 AND ply=(SELECT MAX(ply) FROM positions WHERE game_id=1)"
        )
    result = list_candidates(db, LEARNER)
    assert not result["candidates"]
    assert result["excluded"]
    db.connection.execute("ROLLBACK TO corrupt")
    db.connection.execute("RELEASE corrupt")
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    db.close()


def test_changed_source_marker_fails_closed_during_snapshot(tmp_path, monkeypatch):
    import chess_coach.material_source as module

    db, _ = fixture(tmp_path, monkeypatch)
    original = module.source_marker
    markers = iter((original(db, 1, 1, LEARNER), "changed"))
    monkeypatch.setattr(module, "source_marker", lambda *args: next(markers))
    with preview_history(db, LEARNER) as history:
        history.targets([1])
        with pytest.raises(ValueError, match="source changed during preparation"):
            module.prepare(db, 1, LEARNER, history=history)
    db.close()


@pytest.mark.parametrize("corruption", ["pgn", "variant", "missing_ply"])
def test_history_rejects_corrupt_game_and_new_snapshot_reloads(tmp_path, corruption):
    db = games_db(tmp_path)
    first = db.connection.execute(
        "SELECT id FROM positions WHERE game_id=1 ORDER BY ply"
    ).fetchone()[0]
    db.connection.execute("SAVEPOINT corrupt")
    if corruption == "pgn":
        db.connection.execute("UPDATE games SET pgn=? WHERE id=1", ("",))
    elif corruption == "variant":
        db.connection.execute("UPDATE games SET variant=? WHERE id=1", ("Chess960",))
    else:
        db.connection.execute("DELETE FROM positions WHERE game_id=1 AND ply=4")
    with preview_history(db, LEARNER) as history:
        history.targets([first])
        for _ in range(2):
            with pytest.raises(ValueError):
                history.board(1, first)
    db.connection.execute("ROLLBACK TO corrupt")
    db.connection.execute("RELEASE corrupt")
    with preview_history(db, LEARNER) as history:
        history.targets([first])
        assert history.context(1, first)["subject"] == LEARNER
    db.close()


@pytest.mark.parametrize("source", ["invalid json", "{}", '{"detector_input": null}'])
def test_invalid_source_record_excludes_candidate(tmp_path, monkeypatch, source):
    db, _ = fixture(tmp_path, monkeypatch)
    db.connection.execute("SAVEPOINT corrupt")
    db.connection.execute("UPDATE detector_runs SET input_json=?", (source,))
    result = list_candidates(db, LEARNER)
    assert not result["candidates"]
    assert result["excluded"]
    db.connection.execute("ROLLBACK TO corrupt")
    db.connection.execute("RELEASE corrupt")
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    db.close()


def test_material_verification_limit_fails_closed(tmp_path, monkeypatch):
    import chess_coach.material_source as module

    db, _ = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "MAX_DECISIONS", 1)
    result = list_candidates(db, LEARNER)
    assert not result["candidates"]
    assert result["excluded"]
    db.close()


def test_changed_marker_during_witness_verification_excludes_candidate(tmp_path, monkeypatch):
    import chess_coach.material_opportunity_current as module

    db, _ = fixture(tmp_path, monkeypatch)
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    with monkeypatch.context() as patch:
        patch.setattr(module, "source_marker", lambda *args: "changed")
        result = list_candidates(db, LEARNER)
        assert not result["candidates"]
        assert result["excluded"]
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    db.close()


def test_invalid_witness_cannot_become_preview_candidate(tmp_path, monkeypatch):
    import chess_coach.material_opportunity_current as module

    db, _ = fixture(tmp_path, monkeypatch)
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    with monkeypatch.context() as patch:
        patch.setattr(module, "verified_witness", lambda *args: {"uci": ["a1a8"], "role": "best"})
        result = list_candidates(db, LEARNER)
        assert not result["candidates"]
        assert result["excluded"] == {"stale or unavailable source": 1}
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    db.close()


def test_missing_source_and_decision_fail_closed(tmp_path, monkeypatch):
    from chess_coach.decision_inspection import inspect_decision
    from chess_coach.material_opportunity_source import load_source
    from chess_coach.material_source import prepare

    db, _ = fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="material opportunity unavailable"):
        load_source(db, -1)
    with preview_history(db, LEARNER) as history:
        history.targets([-1])
        with pytest.raises(ValueError, match="decision unavailable"):
            prepare(db, -1, LEARNER, history=history)
        with pytest.raises(ValueError, match="unknown decision"):
            inspect_decision(db, -1, learner=LEARNER, _history=history)
    db.close()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE evidence_mappings SET context_json='null'",
        "UPDATE detector_facts SET payload_json='null'",
        "UPDATE evidence_fact_links SET active=0",
        "UPDATE detector_runs SET status='superseded'",
    ],
)
def test_unusable_evidence_is_excluded_until_restored(tmp_path, monkeypatch, statement):
    db, _ = fixture(tmp_path, monkeypatch)
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    db.connection.execute("SAVEPOINT corrupt")
    db.connection.execute(statement)
    result = list_candidates(db, LEARNER)
    assert not result["candidates"]
    assert result["excluded"]
    db.connection.execute("ROLLBACK TO corrupt")
    db.connection.execute("RELEASE corrupt")
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    db.close()


def test_missing_deep_provenance_excludes_candidate(tmp_path, monkeypatch):
    import chess_coach.material_source as module

    db, _ = fixture(tmp_path, monkeypatch)
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    original = module.inspect_decision

    def missing_attempt(*args, **kwargs):
        analysis = original(*args, **kwargs)
        analysis["deep"] = {
            "status": "complete",
            "result": {"best": analysis["best"], "played": analysis["played"]},
            "job_id": -1,
            "attempt_number": 1,
        }
        return analysis

    with monkeypatch.context() as patch:
        patch.setattr(module, "inspect_decision", missing_attempt)
        result = list_candidates(db, LEARNER)
        assert not result["candidates"]
        assert result["excluded"]
    assert len(list_candidates(db, LEARNER)["candidates"]) == 1
    db.close()


def test_absent_subject_never_opens_snapshot(tmp_path, monkeypatch):
    import chess_coach.unified_own_game as module

    db, _ = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "preview_history", lambda *args: pytest.fail("unexpected snapshot"))
    result = list_candidates(db, "  ")
    assert result["candidates"] == []
    assert result["excluded"] == {"subject unavailable": 1}
    assert result["scanned"] == 0
    db.close()


def test_source_snapshot_reused_only_within_scoped_preview(tmp_path, monkeypatch):
    import chess_coach.preview_sources as sources_module
    from chess_coach.material_source import prepare

    db, _evidence = fixture(tmp_path, monkeypatch)
    original = sources_module.source_snapshot
    calls = []

    def counted(db, game_id, learner):
        calls.append(game_id)
        return original(db, game_id, learner)

    monkeypatch.setattr(sources_module, "source_snapshot", counted)
    with preview_history(db, LEARNER) as history:
        history.targets([1])
        first = prepare(db, 1, LEARNER, history=history)
        second = prepare(db, 1, LEARNER, history=history)
        assert first["source_marker"] == second["source_marker"]
        assert len(calls) == 1
        with pytest.raises(ValueError):
            history.source(2, 1)
        with pytest.raises(ValueError, match="position outside preview"):
            history.source(1, 2)
    assert not history.sources.values
    with pytest.raises(ValueError, match="snapshot is closed"):
        history.source(1, 1)
    with preview_history(db, LEARNER) as history:
        history.targets([1])
        prepare(db, 1, LEARNER, history=history)
    assert len(calls) == 2
    db.close()


def test_source_snapshot_cleared_when_preview_raises(tmp_path, monkeypatch):
    from chess_coach.material_source import prepare

    db, _evidence = fixture(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="stop"), preview_history(db, LEARNER) as history:
        history.targets([1])
        prepare(db, 1, LEARNER, history=history)
        assert history.sources.values
        raise RuntimeError("stop")
    assert not history.sources.values
    assert db.connection.execute("PRAGMA query_only").fetchone()[0] == 0
    db.close()


def test_concurrent_connections_keep_preview_summaries_separate(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock

    import chess_coach.preview_sources as sources_module

    db, _evidence = fixture(tmp_path, monkeypatch)
    db.close()
    barrier, lock, calls = Barrier(2), Lock(), []
    original = sources_module.source_snapshot

    def counted(db, game_id, learner):
        with lock:
            calls.append(game_id)
        return original(db, game_id, learner)

    def preview():
        db = Database(tmp_path / "own.sqlite")
        with preview_history(db, LEARNER) as history:
            history.targets([1])
            barrier.wait(timeout=10)
            first = history.source(1, 1)
            barrier.wait(timeout=10)
            assert history.source(1, 1) == first
        assert not history.sources.values
        db.close()
        return first

    monkeypatch.setattr(sources_module, "source_snapshot", counted)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: preview(), range(2)))
    assert results[0] == results[1]
    assert len(calls) == 2
