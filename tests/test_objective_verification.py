"""Owned, history-bound mate-in-one verification without learning writes."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.mate_auto import process_decision
from chess_coach.mate_contract import MAPPER
from chess_coach.mate_proof import immediate_mates
from chess_coach.objective_contract import VERSION
from chess_coach.objective_publication import cancel
from chess_coach.objective_status import inspect
from chess_coach.objective_verify import compute
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import hint, reveal, show, submit
from chess_coach.unified_sessions import start
from chess_coach.web import create_app
from tests.test_mate_proof import owned_game

FEN = "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"


def fixture(path, monkeypatch, fen=FEN):
    db = owned_game(path, monkeypatch, fen=fen, move="Qe8#")
    process_decision(db, 1, "fixture_a")
    evidence = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE r.producer=?",
        (MAPPER,),
    ).fetchone()[0]
    return db, evidence


def begin(db, evidence, attempt="attempt", subject="fixture_a"):
    return start(
        db,
        attempt_id=attempt,
        subject=subject,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


def answers(db, attempt):
    row = db.connection.execute(
        "SELECT lines_json,prompt_fen FROM unified_sessions WHERE attempt_id=?", (attempt,)
    ).fetchone()
    stored = json.loads(row["lines_json"])[0][0]
    board = chess.Board(row["prompt_fen"])
    other = next(item["uci"] for item in immediate_mates(board) if item["uci"] != stored)
    nonmate = next(move.uci() for move in board.legal_moves if not _mate(board, move))
    return stored, other, nonmate


def _mate(board, move):
    child = board.copy()
    child.push(move)
    return child.is_checkmate()


def test_unlisted_mate_and_nonmate_are_verified_without_rewriting_events(tmp_path, monkeypatch):
    path = tmp_path / "objective.sqlite"
    db, evidence = fixture(path, monkeypatch)
    begin(db, evidence)
    _, other, nonmate = answers(db, "attempt")
    before = db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0]
    pending = submit(db, "attempt", "fixture_a", event_id="move", move=other)
    assert pending["feedback"] == "needs_verification"
    original = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE attempt_id=? AND event_id=?",
        ("attempt", "move"),
    ).fetchone()[0]
    assert show(db, "attempt", "fixture_a")["verification"] == {"status": "pending"}
    assert process(db, "fixture_a")["outcomes"] == {"correct": 1}
    assert show(db, "attempt", "fixture_a")["verification"]["status"] == "correct"
    assert submit(db, "attempt", "fixture_a", event_id="move", move=other) == pending
    assert (
        db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE attempt_id=? AND event_id=?",
            ("attempt", "move"),
        ).fetchone()[0]
        == original
    )
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == before
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    begin(db, evidence, "second")
    submit(db, "second", "fixture_a", event_id="move", move=nonmate)
    assert process(db, "fixture_a")["outcomes"] == {"incorrect": 1}
    assert inspect(db, "fixture_a", "second", "move")["reason"] == "not_immediate_checkmate"
    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="fixture_reviewer",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    response = app.test_client().get(
        "/unified/attempt",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert (
        b"Find checkmate in one move" in response.data
        and b"Correct: this move is checkmate in one" in response.data
    )


def test_assistance_reveal_conflicts_and_illegal_moves(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path / "assistance.sqlite", monkeypatch)
    begin(db, evidence)
    assert hint(db, "attempt", "fixture_a", event_id="hint")["assistance_kind"] == "hinted"
    with pytest.raises(ValueError):
        reveal(db, "attempt", "fixture_a", event_id="hint")
    assert reveal(db, "attempt", "fixture_a", event_id="reveal")["assistance_kind"] == "revealed"
    assert (
        submit(db, "attempt", "fixture_a", event_id="illegal", move="a1a2")["feedback"] == "illegal"
    )
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0
    _, other, _ = answers(db, "attempt")
    submit(db, "attempt", "fixture_a", event_id="move", move=other)
    process(db, "fixture_a")
    result = inspect(db, "fixture_a", "attempt", "move")
    assert result["status"] == "correct" and result["assistance"] == "revealed"
    stored = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert stored["learning_eligible"] is False
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0


def test_revocation_before_and_after_computation_never_publishes_correct(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path / "race.sqlite", monkeypatch)
    begin(db, evidence)
    _, other, _ = answers(db, "attempt")
    submit(db, "attempt", "fixture_a", event_id="move", move=other)

    def revoke_after_compute(db, request, clock, *, seconds):
        result = compute(db, request, clock, seconds=seconds)
        assert result["status"] == "correct"
        review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
        return result

    assert process(db, "fixture_a", verifier=revoke_after_compute)["outcomes"] == {"unresolved": 1}
    raw = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert raw["reason"] == "source_unavailable"
    assert inspect(db, "fixture_a", "attempt", "move")["reason"] == "source_unavailable"
    app = create_app(
        db_path=tmp_path / "race.sqlite",
        subject="fixture_a",
        actor="fixture_reviewer",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        "/unified/attempt",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert page.status_code == 410 and b"source is unavailable or has changed" in page.data


def test_timeout_cancellation_and_unknown_history(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path / "timeout.sqlite", monkeypatch)
    begin(db, evidence)
    _, other, _ = answers(db, "attempt")
    submit(db, "attempt", "fixture_a", event_id="move", move=other)
    times = iter((0.0, 2.0))
    assert process(db, "fixture_a", seconds=1.0, clock=lambda: next(times))["outcomes"] == {
        "unresolved": 1
    }
    assert inspect(db, "fixture_a", "attempt", "move")["reason"] == "timeout"
    begin(db, evidence, "cancel")
    submit(db, "cancel", "fixture_a", event_id="move", move=other)
    assert cancel(db, "fixture_a", "cancel", "move")["reason"] == "cancelled"
    assert process(db, "fixture_a")["processed"] == 0
    with pytest.raises(ValueError):
        cancel(db, "fixture_b", "cancel", "move")
    unknown, item = fixture(
        tmp_path / "history.sqlite", monkeypatch, fen=FEN.replace("0 1", "12 1")
    )
    begin(unknown, item)
    _, other, _ = answers(unknown, "attempt")
    submit(unknown, "attempt", "fixture_a", event_id="move", move=other)
    assert process(unknown, "fixture_a")["outcomes"] == {"unresolved": 1}
    assert inspect(unknown, "fixture_a", "attempt", "move")["reason"] == "history_unavailable"


def test_revocation_before_processing_and_foreign_worker(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path / "before.sqlite", monkeypatch)
    begin(db, evidence, subject="Fixture_A")
    _, other, _ = answers(db, "attempt")
    submit(db, "attempt", "Fixture_A", event_id="move", move=other)
    assert process(db, "fixture_b")["processed"] == 0
    with pytest.raises(ValueError):
        inspect(db, "fixture_b", "attempt", "move")
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    assert process(db, "fixture_a")["outcomes"] == {"unresolved": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert (
        result["reason"] == "source_unavailable" and result["objective_version"] == "mate-in-one-v1"
    )


def test_browser_reveal_is_bound_to_original_event_and_hint_conflicts(tmp_path, monkeypatch):
    from chess_coach.web_practice_reveal import unified_reveal

    db, evidence = fixture(tmp_path / "reveal.sqlite", monkeypatch)
    begin(db, evidence)
    hint(db, "attempt", "fixture_a", event_id="old-hint")
    with pytest.raises(ValueError):
        unified_reveal(db, "attempt", "fixture_a", "old-hint")
    first = unified_reveal(db, "attempt", "fixture_a", "reveal")
    _, other, _ = answers(db, "attempt")
    submit(db, "attempt", "fixture_a", event_id="move", move=other)
    assert unified_reveal(db, "attempt", "fixture_a", "reveal") == first
    process(db, "fixture_a")
    assert inspect(db, "fixture_a", "attempt", "move")["assistance"] == "revealed"


def test_replays_accepted_move_and_reply_and_rejects_claimable_history(tmp_path, monkeypatch):
    from chess_coach.objective_answer import answer
    from chess_coach.objective_history import before_answer
    from chess_coach.objective_judge import _scope_reason

    db, _evidence = fixture(tmp_path / "history-replay.sqlite", monkeypatch)
    board = chess.Board(FEN)
    for first in board.legal_moves:
        trial = board.copy()
        trial.push(first)
        if trial.is_game_over(claim_draw=True):
            continue
        for reply in trial.legal_moves:
            after = trial.copy()
            after.push(reply)
            if not after.is_game_over(claim_draw=True) and any(after.legal_moves):
                break
        else:
            continue
        break
    move = next(iter(after.legal_moves))
    post = after.copy()
    post.push(move)
    events = [
        {
            "kind": "move",
            "submitted_move": first.uci(),
            "response_json": json.dumps(
                {"feedback": "line_match", "opponent_move": reply.uci(), "fen": after.fen()}
            ),
        },
        {
            "kind": "move",
            "submitted_move": move.uci(),
            "response_json": json.dumps({"feedback": "needs_verification", "fen": post.fen()}),
        },
    ]
    session = {
        "provenance_json": json.dumps({"position_id": 1}),
        "prompt_fen": board.fen(),
        "current_fen": post.fen(),
    }
    reconstructed, answer_move = before_answer(db, session, events)
    assert [item.uci() for item in reconstructed.move_stack] == [first.uci(), reply.uci()]
    assert (
        answer_move == move
        and _scope_reason(reconstructed, {"learner_color": "white"}, events)
        == "objective_horizon_changed"
    )
    with pytest.raises(ValueError, match="move unavailable"):
        answer(
            chess.Board(),
            {},
            {
                "kind": "move",
                "submitted_move": "0000",
                "response_json": json.dumps({"feedback": "needs_verification"}),
            },
        )
    repeated = chess.Board()
    for uci in ("g1f3", "g8f6", "f3g1", "f6g8") * 2:
        repeated.push_uci(uci)
    assert repeated.can_claim_threefold_repetition()
    with pytest.raises(ValueError, match="claimable"):
        answer(
            repeated,
            {},
            {
                "kind": "move",
                "submitted_move": "g1f3",
                "response_json": json.dumps({"feedback": "needs_verification"}),
            },
        )


def test_historical_hint_kind_remains_unknown():
    from chess_coach.objective_events import assistance

    old = {"kind": "hint", "response_json": json.dumps({"feedback": "hint"})}
    assert assistance([old]) == "assisted_unknown"


def test_black_owned_alternative_and_immutable_results(tmp_path, monkeypatch):
    import sqlite3

    board = chess.Board(FEN).mirror()
    move = chess.Move.from_uci(immediate_mates(board)[0]["uci"])
    db = owned_game(tmp_path / "black.sqlite", monkeypatch, fen=board.fen(), move=board.san(move))
    process_decision(db, 1, "fixture_b")
    evidence = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE r.producer=?",
        (MAPPER,),
    ).fetchone()[0]
    begin(db, evidence, subject="fixture_b")
    _, other, _ = answers(db, "attempt")
    submit(db, "attempt", "fixture_b", event_id="move", move=other)
    assert process(db, "fixture_b")["outcomes"] == {"correct": 1}
    with pytest.raises(sqlite3.IntegrityError):
        db.connection.execute("UPDATE objective_results SET result_json=?", ("{}",))
    db.connection.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        db.connection.execute("DELETE FROM objective_requests")
    db.connection.rollback()
    assert inspect(db, "fixture_b", "attempt", "move")["status"] == "correct"


def test_pipeline_runs_bounded_verification(tmp_path, monkeypatch):
    import sys

    import httpx

    from chess_coach.pipeline import process_pipeline
    from chess_coach.pipeline_config import PipelineConfig

    db, evidence = fixture(tmp_path / "pipeline.sqlite", monkeypatch)
    begin(db, evidence)
    _, other, _ = answers(db, "attempt")
    submit(db, "attempt", "fixture_a", event_id="move", move=other)
    config = PipelineConfig(
        learner="fixture_a",
        engine_path=sys.executable,
        nodes=100,
        deep_enabled=False,
        mate_enabled=False,
        pawn_enabled=False,
    )
    result = process_pipeline(
        db, config, transport=httpx.MockTransport(lambda request: httpx.Response(200))
    )
    assert result["objective_verification"]["outcomes"] == {"correct": 1}


@pytest.mark.parametrize("deadline", [None, "2099-01-01T00:00:00+00:00"])
def test_retry_worker_processes_local_jobs_without_network_or_cooldown_changes(
    tmp_path, monkeypatch, capsys, deadline
):
    from chess_coach import ops_retry, pipeline_sync
    from chess_coach.db import Database
    from chess_coach.pipeline_health import start_run

    path = tmp_path / "retry.sqlite"
    db, evidence = fixture(path, monkeypatch)
    begin(db, evidence)
    _, other, _ = answers(db, "attempt")
    submit(db, "attempt", "fixture_a", event_id="move", move=other)
    start_run(db)
    db.connection.execute("UPDATE pipeline_health SET retry_until=? WHERE id=1", (deadline,))
    db.connection.commit()
    before = tuple(db.connection.execute("SELECT * FROM pipeline_health WHERE id=1").fetchone())
    db.close()
    calls = []
    monkeypatch.setenv("LICHESS_USERNAME", "fixture_a")
    monkeypatch.setattr(ops_retry, "database_path", lambda: path)
    monkeypatch.setattr(pipeline_sync, "sync_games", lambda *args, **kwargs: calls.append(True))
    ops_retry.main()
    assert not calls and capsys.readouterr().out == ""
    db = Database(path)
    assert (
        tuple(db.connection.execute("SELECT * FROM pipeline_health WHERE id=1").fetchone())
        == before
    )
    assert inspect(db, "fixture_a", "attempt", "move")["status"] == "correct"
    db.close()


def test_source_scope_and_size_limits_are_enforced(tmp_path, monkeypatch):
    from chess_coach.objective_mate_source import resolve

    db, evidence = fixture(tmp_path / "source-boundary.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        resolve(db, VERSION, str(evidence), "fixture_b")
    db.connection.execute(
        "UPDATE mapping_runs SET scope_key=? WHERE id=(SELECT mapping_run_id FROM evidence_mappings WHERE id=?)",
        ("unrelated", evidence),
    )
    db.connection.commit()
    with pytest.raises(ValueError):
        resolve(db, VERSION, str(evidence), "fixture_a")
    large, evidence = fixture(tmp_path / "large.sqlite", monkeypatch)
    large.connection.execute("UPDATE games SET pgn=? WHERE id=1", ("x" * 1_000_001,))
    large.connection.commit()
    with pytest.raises(ValueError):
        resolve(large, VERSION, str(evidence), "fixture_a")


def test_future_composition_mode_is_explicitly_unsupported_for_this_verifier(monkeypatch):
    from chess_coach import objective_verify
    from chess_coach.objective_contract import STANDALONE

    monkeypatch.setattr(objective_verify, "current", lambda *args: (None, []))
    request = {
        "objective_version": "mate-in-one-v1",
        "history_mode": STANDALONE,
        "snapshot_hash": "fixture",
        "event_prefix_hash": "fixture",
        "source_hash": "fixture",
    }
    result = objective_verify.compute(None, request, lambda: 0.0)
    assert result["status"] == "unresolved" and result["reason"] == "history_mode_not_supported"


def test_revocation_after_result_keeps_history_but_hides_stale_claim(tmp_path, monkeypatch):
    path = tmp_path / "after-result.sqlite"
    db, evidence = fixture(path, monkeypatch)
    begin(db, evidence)
    _, other, _ = answers(db, "attempt")
    submit(db, "attempt", "fixture_a", event_id="move", move=other)
    process(db, "fixture_a")
    stored = db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    assert json.loads(stored)["status"] == "correct"
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    assert inspect(db, "fixture_a", "attempt", "move")["reason"] == "source_unavailable"
    assert (
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0] == stored
    )
    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="fixture_reviewer",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    page = app.test_client().get(
        "/unified/attempt",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert page.status_code == 410 and b"Correct: this move" not in page.data


def test_malformed_assistance_history_stays_unresolved(monkeypatch):
    from chess_coach import objective_verify
    from chess_coach.objective_contract import OWNED_HISTORY

    events = [{"kind": "hint", "response_json": "{"}, {"kind": "move"}]
    monkeypatch.setattr(objective_verify, "current", lambda *args: (None, events))
    request = {
        "objective_version": "mate-in-one-v1",
        "history_mode": OWNED_HISTORY,
        "snapshot_hash": "fixture",
        "event_prefix_hash": "fixture",
        "source_hash": "fixture",
    }
    result = objective_verify.compute(None, request, lambda: 0.0)
    assert result["status"] == "unresolved" and result["reason"] == "source_unavailable"


def test_private_library_pending_and_worker_retry_after_atomic_failure(tmp_path, monkeypatch):
    from chess_coach import objective_publication
    from chess_coach.objective_current import current
    from chess_coach.objective_mate_list import candidates

    path = tmp_path / "atomic.sqlite"
    db, evidence = fixture(path, monkeypatch)
    assert not candidates(db, "fixture_b")["candidates"]
    app = create_app(
        db_path=path,
        subject="fixture_a",
        actor="fixture_reviewer",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    page = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert b"Verify and practice mate in one" in page.data
    begin(db, evidence)
    _, other, _ = answers(db, "attempt")
    submit(db, "attempt", "fixture_a", event_id="move", move=other)
    page = client.get("/unified/attempt", base_url="https://coach.invalid", headers=headers)
    assert b"Verification is queued" in page.data
    request = db.connection.execute("SELECT * FROM objective_requests").fetchone()
    with pytest.raises(ValueError, match="history changed"):
        current(db, {**dict(request), "event_prefix_hash": "altered"})
    with monkeypatch.context() as patch:
        patch.setattr(
            objective_publication,
            "_insert",
            lambda *args: (_ for _ in ()).throw(RuntimeError("fixture failure")),
        )
        with pytest.raises(RuntimeError, match="fixture failure"):
            process(db, "fixture_a")
    assert not db.connection.in_transaction
    assert db.connection.execute("SELECT COUNT(*) FROM objective_results").fetchone()[0] == 0
    assert process(db, "fixture_a")["outcomes"] == {"correct": 1}
    replay = objective_publication.publish(db, request, {"status": "incorrect"})
    assert replay["status"] == "correct"
    assert cancel(db, "fixture_a", "attempt", "move")["status"] == "correct"


def test_invalid_event_and_worker_boundaries_are_rejected(tmp_path, monkeypatch):
    from chess_coach.objective_events import prefix, response
    from chess_coach.objective_history_replay import replay

    db, _evidence = fixture(tmp_path / "invalid.sqlite", monkeypatch)
    with pytest.raises(ValueError, match="event unavailable"):
        prefix(db, "missing", "missing")
    with pytest.raises(ValueError, match="event unavailable"):
        response({"response_json": "{"})
    with pytest.raises(ValueError, match="worker limits"):
        process(db, "fixture_a", limit=0)
    db.connection.execute("BEGIN")
    with pytest.raises(RuntimeError, match="idle database"):
        process(db, "fixture_a")
    db.connection.rollback()
    board = chess.Board()
    event = {
        "kind": "move",
        "submitted_move": "0000",
        "response_json": json.dumps({"feedback": "line_match", "fen": board.fen()}),
    }
    with pytest.raises(ValueError, match="history unavailable"):
        replay(board, event)
    event = {
        "kind": "hint",
        "submitted_move": None,
        "response_json": json.dumps({"feedback": "hint", "fen": "different"}),
    }
    with pytest.raises(ValueError, match="history changed"):
        replay(board, event)
