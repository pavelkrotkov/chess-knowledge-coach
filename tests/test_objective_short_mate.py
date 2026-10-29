"""Owned short-mate alternatives preserve proof, history and playable state."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.mate_auto import process_decision
from chess_coach.mate_contract import MAPPER
from chess_coach.objective_short_source import VERSION
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import hint, reveal, show, submit
from chess_coach.unified_sessions import start
from chess_coach.web import create_app
from tests.test_mate_proof import owned_game

WHITE = "7k/5Q2/6K1/8/8/8/8/8 w - - 0 1"
BLACK = chess.Board(WHITE).mirror().fen()


def fixture(path, monkeypatch, black=False):
    subject = "fixture_b" if black else "fixture_a"
    db = owned_game(
        path, monkeypatch, fen=BLACK if black else WHITE, move="Qa2" if black else "Qa7"
    )
    process_decision(db, 1, subject)
    evidence = db.connection.execute(
        "SELECT e.id FROM evidence_mappings e JOIN mapping_runs r ON r.id=e.mapping_run_id WHERE r.producer=?",
        (MAPPER,),
    ).fetchone()[0]
    return db, evidence, subject


def begin(db, evidence, subject, attempt="attempt"):
    return start(
        db,
        attempt_id=attempt,
        subject=subject,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


def alternative(db, attempt):
    row = db.connection.execute(
        "SELECT lines_json,provenance_json FROM unified_sessions WHERE attempt_id=?", (attempt,)
    ).fetchone()
    root = json.loads(row["lines_json"])[0][0]
    fact = db.connection.execute(
        "SELECT payload_json FROM detector_facts WHERE id=(SELECT fact_id FROM evidence_fact_links WHERE evidence_id=?)",
        (json.loads(row["provenance_json"])["evidence_id"],),
    ).fetchone()
    proof = json.loads(fact[0])["proof"]
    return next(
        item["move"]["uci"]
        for item in proof["alternatives"]
        if item["status"] == "proved"
        and item["distance_plies"] == 3
        and item["move"]["uci"] != root
    )


@pytest.mark.parametrize("black", [False, True])
def test_proved_alternative_is_playable_and_only_actual_mate_completes(
    tmp_path, monkeypatch, black
):
    db, evidence, subject = fixture(tmp_path / "fixture.sqlite", monkeypatch, black)
    begin(db, evidence, subject)
    answer = alternative(db, "attempt")
    pending = submit(db, "attempt", subject, event_id="answer", move=answer)
    assert pending["status"] == "needs_verification"
    frozen = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE event_id=?", ("answer",)
    ).fetchone()[0]
    assert process(db, subject)["outcomes"] == {"correct": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["proof"]["distance_plies"] == 3 and result["learning_eligible"] is False
    changes = db.connection.total_changes
    state = show(db, "attempt", subject)
    assert state["status"] == "active" and state["proved_continuation"]
    assert show(db, "attempt", subject) == state
    assert db.connection.total_changes == changes
    assert process(db, subject)["processed"] == 0
    assert submit(db, "attempt", subject, event_id="answer", move=answer) == pending
    assert (
        db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE event_id=?", ("answer",)
        ).fetchone()[0]
        == frozen
    )
    assert hint(db, "attempt", subject, event_id="hint")["assistance_kind"] == "hinted"
    revealed = reveal(db, "attempt", subject, event_id="reveal")
    assert revealed["assistance_kind"] == "revealed"
    mate = revealed["revealed_line"]
    assert chess.Board(state["fen"]).parse_uci(mate) in chess.Board(state["fen"]).legal_moves
    completed = submit(db, "attempt", subject, event_id="finish", move=mate)
    assert (
        completed["status"] == "objective_verified" and chess.Board(completed["fen"]).is_checkmate()
    )
    assert submit(db, "attempt", subject, event_id="finish", move=mate) == completed
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    app = create_app(
        db_path=tmp_path / "fixture.sqlite",
        subject=subject,
        actor="fixture",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    response = app.test_client().get(
        "/unified/attempt",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    assert response.status_code == 200 and b"checkmate objective was verified" in response.data


def test_refutation_timeout_and_stale_source_are_unresolved_or_incorrect(tmp_path, monkeypatch):
    db, evidence, subject = fixture(tmp_path / "negative.sqlite", monkeypatch)
    begin(db, evidence, subject)
    board = chess.Board(WHITE)
    move = next(
        m
        for m in board.legal_moves
        if m.uci()
        not in json.loads(
            db.connection.execute("SELECT lines_json FROM unified_sessions").fetchone()[0]
        )[0]
        and _refuted(board, m)
    )
    submit(db, "attempt", subject, event_id="answer", move=move.uci())
    assert process(db, subject)["outcomes"] == {"incorrect": 1}
    assert inspect(db, subject, "attempt", "answer")["reason"] == "refuted_within_two"
    begin(db, evidence, subject, "timeout")
    submit(db, "timeout", subject, event_id="answer", move=alternative(db, "timeout"))
    ticks = iter([0.0] + [10.0] * 10000)
    assert process(db, subject, clock=lambda: next(ticks))["outcomes"] == {"unresolved": 1}
    assert inspect(db, subject, "timeout", "answer")["reason"] == "timeout"
    begin(db, evidence, subject, "stale")
    submit(db, "stale", subject, event_id="answer", move=alternative(db, "stale"))
    review_evidence(db, evidence, decision="reject", actor="reviewer")
    assert process(db, subject)["outcomes"] == {"unresolved": 1}
    with pytest.raises(ValueError):
        show(db, "stale", subject)


def _refuted(board, move):
    from chess_coach.mate_proof import Budget, _root

    return _root(board, move, Budget())["status"] == "disproved"


def test_revoke_after_proof_blocks_resume_and_preserves_prior_response(tmp_path, monkeypatch):
    db, evidence, subject = fixture(tmp_path / "revoked.sqlite", monkeypatch)
    begin(db, evidence, subject)
    move = alternative(db, "attempt")
    original = submit(db, "attempt", subject, event_id="answer", move=move)
    assert process(db, subject)["outcomes"] == {"correct": 1}
    mate = reveal(db, "attempt", subject, event_id="reveal")["revealed_line"]
    before = db.connection.execute("SELECT COUNT(*) FROM unified_session_events").fetchone()[0]
    review_evidence(db, evidence, decision="reject", actor="reviewer")
    with pytest.raises(ValueError):
        submit(db, "attempt", subject, event_id="finish", move=mate)
    assert (
        db.connection.execute("SELECT COUNT(*) FROM unified_session_events").fetchone()[0] == before
    )
    stored = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE event_id=?", ("answer",)
    ).fetchone()[0]
    assert json.loads(stored) == original


def test_revoke_between_computation_and_publication_does_not_publish_proof(tmp_path, monkeypatch):
    from chess_coach.objective_verify import compute

    db, evidence, subject = fixture(tmp_path / "race.sqlite", monkeypatch)
    begin(db, evidence, subject)
    submit(db, "attempt", subject, event_id="answer", move=alternative(db, "attempt"))

    def verifier(database, request, clock, *, seconds):
        result = compute(database, request, clock, seconds=seconds)
        assert result["status"] == "correct"
        review_evidence(database, evidence, decision="reject", actor="reviewer")
        return result

    assert process(db, subject, verifier=verifier)["outcomes"] == {"unresolved": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["reason"] == "source_unavailable" and "proof" not in result


def test_budget_exhaustion_and_repetition_do_not_create_false_correct(monkeypatch):
    import chess_coach.objective_short_judge as judge
    from chess_coach.mate_proof import Budget, _root

    board = chess.Board(WHITE)
    monkeypatch.setattr(judge, "MAX_NODES", 1)
    result = judge.judge(board, board.parse_uci("f7a7"), lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "unresolved" and result["reason"] == "proof_budget"
    repeated = chess.Board()
    for move in ("g1f3", "g8f6", "f3g1", "f6g8") * 2:
        repeated.push_uci(move)
    assert repeated.can_claim_threefold_repetition()
    assert _root(repeated, repeated.parse_uci("g1f3"), Budget(200))["status"] == "disproved"


def test_immediate_mate_alternative_completes_only_after_actual_move(tmp_path, monkeypatch):
    from chess_coach.mate_proof import immediate_mates

    db, evidence, subject = fixture(tmp_path / "immediate.sqlite", monkeypatch)
    begin(db, evidence, subject)
    move = immediate_mates(chess.Board(WHITE))[0]["uci"]
    pending = submit(db, "attempt", subject, event_id="answer", move=move)
    assert pending["status"] == "needs_verification"
    assert process(db, subject)["outcomes"] == {"correct": 1}
    state = show(db, "attempt", subject)
    assert state["status"] == "objective_verified" and chess.Board(state["fen"]).is_checkmate()
    assert submit(db, "attempt", subject, event_id="answer", move=move) == pending


def test_existing_retry_processes_short_mate_during_cooldown_without_network(
    tmp_path, monkeypatch, capsys
):
    from chess_coach import ops_retry, pipeline_sync
    from chess_coach.db import Database
    from chess_coach.pipeline_health import start_run

    path = tmp_path / "retry.sqlite"
    db, evidence, subject = fixture(path, monkeypatch)
    begin(db, evidence, subject)
    submit(db, "attempt", subject, event_id="answer", move=alternative(db, "attempt"))
    start_run(db)
    db.connection.execute(
        "UPDATE pipeline_health SET retry_until=? WHERE id=1", ("2099-01-01T00:00:00+00:00",)
    )
    db.connection.commit()
    before = tuple(db.connection.execute("SELECT * FROM pipeline_health WHERE id=1").fetchone())
    db.close()
    calls = []
    monkeypatch.setenv("LICHESS_USERNAME", subject)
    monkeypatch.setattr(ops_retry, "database_path", lambda: path)
    monkeypatch.setattr(pipeline_sync, "sync_games", lambda *args, **kwargs: calls.append(True))
    ops_retry.main()
    assert not calls and capsys.readouterr().out == ""
    db = Database(path)
    assert (
        tuple(db.connection.execute("SELECT * FROM pipeline_health WHERE id=1").fetchone())
        == before
    )
    assert show(db, "attempt", subject)["proved_continuation"]


def test_owned_history_is_reconstructed_before_and_after_defense(tmp_path, monkeypatch):
    import sys

    import chess.engine

    from chess_coach.db import Database
    from chess_coach.decision_history import decision_board
    from chess_coach.ingest import ingest_pgn
    from chess_coach.mate_inspection_source import position_row
    from chess_coach.objective_short_continue import continuation
    from chess_coach.pipeline_config import PipelineConfig
    from chess_coach.pipeline_inputs import engine_identity, game_input
    from chess_coach.pipeline_work import run_analysis
    from chess_coach.unified_session_state import session_row
    from tests.test_mate_proof import Engine

    path = tmp_path / "history.sqlite"
    db = Database(path)
    db.initialize()
    pgn = """[Event \"Synthetic\"]
[White \"fixture_a\"]
[Black \"fixture_b\"]
[SetUp \"1\"]
[FEN \"6k1/5Q2/6K1/8/8/8/8/8 b - - 0 1\"]
[Result \"*\"]

1... Kh8 2. Qa7 *
"""
    ingest_pgn(db, pgn)
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(learner="fixture_a", engine_path=sys.executable, nodes=100)
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    position = db.connection.execute("SELECT id FROM positions WHERE uci=?", ("f7a7",)).fetchone()[
        0
    ]
    board = decision_board(db, position_row(db, position))
    assert [m.uci() for m in board.move_stack] == ["g8h8"]
    process_decision(db, position, "fixture_a")
    evidence = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE position_id=?", (position,)
    ).fetchone()[0]
    begin(db, evidence, "fixture_a")
    submit(db, "attempt", "fixture_a", event_id="answer", move=alternative(db, "attempt"))
    assert process(db, "fixture_a")["outcomes"] == {"correct": 1}
    resumed = continuation(db, session_row(db, "attempt", "fixture_a"))
    assert [m.uci() for m in resumed["board"].move_stack][:1] == ["g8h8"]
    assert len(resumed["board"].move_stack) == 3
    assert resumed["board"].move_stack[-1].uci() == resumed["defense"]


def test_source_with_no_immediate_mate_accepts_a_second_forced_root(tmp_path, monkeypatch):
    from chess_coach import mate_auto
    from chess_coach.mate_proof import immediate_mates

    fen = "4K2k/8/8/8/8/8/8/6Q1 w - - 0 1"
    assert immediate_mates(chess.Board(fen)) == []
    db = owned_game(tmp_path / "no-immediate.sqlite", monkeypatch, fen=fen, move="Kf7")
    monkeypatch.setattr(mate_auto, "short_candidate", lambda *_: True)
    process_decision(db, 1, "fixture_a")
    evidence = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE position_id=1"
    ).fetchone()[0]
    begin(db, evidence, "fixture_a")
    submit(db, "attempt", "fixture_a", event_id="answer", move=alternative(db, "attempt"))
    assert process(db, "fixture_a")["outcomes"] == {"correct": 1}
    state = show(db, "attempt", "fixture_a")
    assert state["status"] == "active" and state["proved_continuation"]


def test_continuation_illegal_and_nonmate_moves_are_not_checkmate(tmp_path, monkeypatch):
    db, evidence, subject = fixture(tmp_path / "continuation-errors.sqlite", monkeypatch)
    begin(db, evidence, subject)
    submit(db, "attempt", subject, event_id="answer", move=alternative(db, "attempt"))
    assert process(db, subject)["outcomes"] == {"correct": 1}
    state = show(db, "attempt", subject)
    assert submit(db, "attempt", subject, event_id="illegal", move="a1a2")["feedback"] == "illegal"
    assert show(db, "attempt", subject)["fen"] == state["fen"]
    board = chess.Board(state["fen"])
    nonmate = next(move for move in board.legal_moves if not _is_mate(board, move))
    response = submit(db, "attempt", subject, event_id="nonmate", move=nonmate.uci())
    assert response["feedback"] == "incorrect" and response["status"] == "line_completed"
    assert show(db, "attempt", subject)["status"] != "objective_verified"
    with pytest.raises(ValueError):
        submit(db, "attempt", subject, event_id="nonmate", move="a1a2")


def _is_mate(board, move):
    child = board.copy()
    child.push(move)
    return child.is_checkmate()


def test_resume_rejects_mismatched_proof_provenance(tmp_path, monkeypatch):
    from chess_coach.objective_verify import compute

    db, evidence, subject = fixture(tmp_path / "wrong-proof.sqlite", monkeypatch)
    begin(db, evidence, subject)
    submit(db, "attempt", subject, event_id="answer", move=alternative(db, "attempt"))

    def verifier(database, request, clock, *, seconds):
        return compute(database, request, clock, seconds=seconds) | {"proof_version": "old"}

    assert process(db, subject, verifier=verifier)["outcomes"] == {"correct": 1}
    with pytest.raises(ValueError, match="proof version"):
        show(db, "attempt", subject)


@pytest.mark.parametrize("black", [False, True])
def test_unlisted_final_mate_uses_remaining_one_ply_without_search(tmp_path, monkeypatch, black):
    from chess_coach import objective_short_judge
    from chess_coach.mate_proof import immediate_mates

    db, evidence, subject = fixture(tmp_path / "final.sqlite", monkeypatch, black)
    begin(db, evidence, subject)
    row = db.connection.execute(
        "SELECT lines_json FROM unified_sessions WHERE attempt_id=?", ("attempt",)
    ).fetchone()
    lines = json.loads(row["lines_json"])
    first = submit(db, "attempt", subject, event_id="first", move=lines[0][0])
    assert first["status"] == "active" and first["opponent_move"]
    board = chess.Board(first["fen"])
    stored = {line[2] for line in lines if line[1] == first["opponent_move"]}
    other = next(m["uci"] for m in immediate_mates(board) if m["uci"] not in stored)
    original = submit(db, "attempt", subject, event_id="final", move=other)
    assert original["feedback"] == "needs_verification" and board.turn == (not black)
    monkeypatch.setattr(
        objective_short_judge, "_root", lambda *_: pytest.fail("final ply must not search")
    )
    assert process(db, subject)["outcomes"] == {"correct": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["limits"]["plies"] == 1 and result["reason"] == "immediate_checkmate"
    state = show(db, "attempt", subject)
    assert state["status"] == "objective_verified" and chess.Board(state["fen"]).is_checkmate()
    assert submit(db, "attempt", subject, event_id="final", move=other) == original
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
