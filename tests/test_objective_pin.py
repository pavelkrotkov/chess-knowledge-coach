"""Owned pin practice preserves source-bound, limited proof and immutable results."""

import json
import sys

import chess
import chess.engine
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.objective_pin_contract import VERSION
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.pin_pipeline import process_decision
from chess_coach.pipeline_config import PipelineConfig
from chess_coach.pipeline_inputs import engine_identity, game_input
from chess_coach.pipeline_work import run_analysis
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from chess_coach.web import create_app
from tests.test_pin_pipeline import Engine

SUBJECT = "fixture_learner"
ABSOLUTE = "2k5/3r1N2/N1n1B2p/3P4/1Q6/8/8/1R1K4 w - - 0 1"
RELATIVE = "4r2k/b1p5/Bpnppppp/8/8/8/8/7K w - - 0 1"


def owned_pin(path, monkeypatch, *, black=False, relative=False, unknown_history=False):
    board = chess.Board(RELATIVE if relative else ABSOLUTE)
    move = chess.Move.from_uci("a6b5" if relative else "b4c4")
    if black:
        board = board.mirror()
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    if unknown_history:
        board.halfmove_clock = 1
    game = chess.pgn.Game.from_board(board)
    game.headers.update(
        {
            "White": "fixture_opponent" if black else SUBJECT,
            "Black": SUBJECT if black else "fixture_opponent",
            "Result": "*",
        }
    )
    node = game.add_variation(move)
    board.push(move)
    node.add_variation(next(iter(board.legal_moves)))
    db = Database(path)
    db.initialize()
    ingest_pgn(db, str(game))
    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _: Engine())
    config = PipelineConfig(
        learner=SUBJECT, engine_path=sys.executable, nodes=100, deep_enabled=False
    )
    assert (
        run_analysis(db, 1, game_input(db, 1), config, engine_identity(sys.executable))["status"]
        == "complete"
    )
    result = process_decision(db, 1, SUBJECT, "execute")
    assert result["outcome"] == "success"
    return db, result["evidence_ids"][0]


def begin(db, evidence, attempt="pin"):
    return start(
        db,
        attempt_id=attempt,
        subject=SUBJECT,
        source_type="own-game",
        version=VERSION,
        key=str(evidence),
    )


@pytest.mark.parametrize("black", [False, True])
def test_alternative_pin_is_proved_without_rewriting_response_or_learning(
    tmp_path, monkeypatch, black
):
    db, evidence = owned_pin(tmp_path / "owned.sqlite", monkeypatch, black=black)
    before = {
        name: db.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
        for name in (
            "evidence_mappings",
            "evidence_review_events",
            "mastery_events",
            "mastery_states",
            "training_items",
            "training_attempts",
            "training_completions",
        )
    }
    state = begin(db, evidence)
    original = chess.Move.from_uci("b4c4")
    alternative = chess.Move.from_uci("b4c5")
    if black:
        original = chess.Move(
            chess.square_mirror(original.from_square), chess.square_mirror(original.to_square)
        )
        alternative = chess.Move(
            chess.square_mirror(alternative.from_square), chess.square_mirror(alternative.to_square)
        )
    assert original.uci() != alternative.uci()
    assert original.uci() not in json.dumps(state)
    answer = submit(db, "pin", SUBJECT, event_id="answer", move=alternative.uci())
    assert answer["feedback"] == "needs_verification"
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    assert inspect(db, SUBJECT, "pin", "answer")["status"] == "correct"
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["proof"]["type"] == "absolute_pin"
    assert result["proof"]["move"] == alternative.uci()
    assert result["proof"]["pinner"] != state["pin_attacker"]
    assert show(db, "pin", SUBJECT)["verification"]["status"] == "correct"
    assert submit(db, "pin", SUBJECT, event_id="answer", move=alternative.uci()) == answer
    assert {
        name: db.connection.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in before
    } == before


def test_relative_pin_and_unproved_legal_answer_stay_unresolved(tmp_path, monkeypatch):
    db, evidence = owned_pin(tmp_path / "relative.sqlite", monkeypatch, relative=True)
    state = begin(db, evidence)
    assert state["pin_type"] == "relative_pin"
    move = next(move for move in chess.Board(state["fen"]).legal_moves if move.uci() != "a6b5")
    submit(db, "pin", SUBJECT, event_id="answer", move=move.uci())
    assert process(db, SUBJECT)["outcomes"] == {"unresolved": 1}
    assert inspect(db, SUBJECT, "pin", "answer")["status"] == "unresolved"


def test_foreign_and_review_changed_sources_cannot_publish_old_proof(tmp_path, monkeypatch):
    db, evidence = owned_pin(tmp_path / "stale.sqlite", monkeypatch)
    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="foreign",
            subject="other",
            source_type="own-game",
            version=VERSION,
            key=str(evidence),
        )
    begin(db, evidence)
    submit(db, "pin", SUBJECT, event_id="answer", move="b4c5")
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    assert process(db, SUBJECT)["outcomes"] == {"unresolved": 1}
    with pytest.raises(ValueError):
        show(db, "pin", SUBJECT)


def test_browser_evidence_and_cli_start_owned_pin(tmp_path, monkeypatch, capsys):
    from chess_coach.cli import main

    path = tmp_path / "browser.sqlite"
    db, evidence = owned_pin(path, monkeypatch)
    db.close()
    monkeypatch.setattr(
        sys, "argv", ["chess-coach", "--db", str(path), "list-pin-practice", "--subject", SUBJECT]
    )
    main()
    assert json.loads(capsys.readouterr().out)["candidates"] == [{"key": str(evidence)}]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "start-unified",
            "--attempt",
            "cli",
            "--subject",
            SUBJECT,
            "--source",
            "own-game",
            "--version",
            VERSION,
            "--key",
            str(evidence),
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["objective"] == "execute_named_pin"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "chess-coach",
            "--db",
            str(path),
            "move-unified",
            "--attempt",
            "cli",
            "--subject",
            SUBJECT,
            "--event",
            "cli-answer",
            "--move",
            "b4c5",
        ],
    )
    main()
    assert json.loads(capsys.readouterr().out)["feedback"] == "needs_verification"
    monkeypatch.setattr(
        sys,
        "argv",
        ["chess-coach", "--db", str(path), "process-objective-verifications", "--subject", SUBJECT],
    )
    main()
    assert json.loads(capsys.readouterr().out)["outcomes"] == {"correct": 1}
    app = create_app(
        db_path=path,
        subject=SUBJECT,
        actor="fixture_reviewer",
        corpus="fixture",
        login="fixture-login",
        origin="https://coach.invalid",
    )
    app.testing = True
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture-login", "Origin": "https://coach.invalid"}
    response = client.get(
        f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers
    )
    assert response.status_code == 200 and b"Practice this pin" in response.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    response = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers,
        data={"csrf": csrf, "source_type": "own-game", "version": VERSION, "key": str(evidence)},
    )
    assert response.status_code == 303
    page = client.get(
        response.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert page.status_code == 200 and b"Execute the named pin" in page.data
    assert b"b4c4" not in page.data and b"b4c5" not in page.data

    with client.session_transaction(base_url="https://coach.invalid") as session:
        attempt = session["unified_attempt"]
    played = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers,
        data={"csrf": csrf, "attempt": attempt, "event": "browser-answer", "move": "b4c5"},
    )
    assert played.status_code == 303
    queued = client.get(
        played.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Verification queued" in queued.data
    worker = Database(path)
    assert process(worker, SUBJECT)["outcomes"] == {"correct": 1}
    worker.close()
    verified = client.get(
        played.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"bounded material-or-mate consequence are proved" in verified.data


def test_publication_rechecks_review_after_computation(tmp_path, monkeypatch):
    import time

    from chess_coach.objective_publication import publish
    from chess_coach.objective_verify import compute

    db, evidence = owned_pin(tmp_path / "race.sqlite", monkeypatch)
    begin(db, evidence)
    original = submit(db, "pin", SUBJECT, event_id="answer", move="b4c5")
    request = db.connection.execute("SELECT * FROM objective_requests").fetchone()
    computed = compute(db, request, time.monotonic)
    assert computed["status"] == "correct"
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    result = publish(db, request, computed)
    assert result["status"] == "unresolved" and result["reason"] == "source_unavailable"
    assert (
        json.loads(
            db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
        )
        == original
    )
    assert publish(db, request, computed) == result


def test_bound_pin_judge_preserves_uncertainty_and_clock_budget():
    from chess_coach.objective_pin_judge import verify

    board = chess.Board(ABSOLUTE)
    request = {"learner_color": "white"}
    binding = {
        "pin_attacker": "b4",
        "pin_pinned": "c6",
        "pin_rear": "c8",
        "pin_type": "absolute_pin",
    }
    exemplar = chess.Move.from_uci("b4c4")
    assert verify(board, exemplar, request, [], lambda: 6, 0, 5, {}, binding)["reason"] == "timeout"
    missing = {**binding, "pin_type": "unknown"}
    assert (
        verify(board, exemplar, request, [], lambda: 0, 0, 5, {}, missing)["status"] == "unresolved"
    )
    unsupported = chess.Move.from_uci("b4b7")
    assert board.gives_check(unsupported)
    assert (
        verify(board, unsupported, request, [], lambda: 0, 0, 5, {}, binding)["status"]
        == "unresolved"
    )


def test_missing_relevant_history_does_not_admit_pin(tmp_path, monkeypatch):
    db, evidence = owned_pin(tmp_path / "history.sqlite", monkeypatch, unknown_history=True)
    with pytest.raises(ValueError, match="history unavailable"):
        begin(db, evidence)


def test_grounded_pin_lesson_links_to_source_bound_practice(tmp_path):
    from flask import render_template

    app = create_app(
        db_path=tmp_path / "unused.sqlite",
        subject="fixture",
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    lesson = {
        "family": "pin-execute-mapper",
        "qualification": "bounded",
        "possible": "possible",
        "question": "question",
        "habit": "habit",
        "practice": "practice",
        "examples": [
            {
                "evidence_id": 1,
                "position_id": 1,
                "game_id": 1,
                "ply": 1,
                "review": "unreviewed",
                "played": "move",
                "operation": "execute",
                "facts": [],
                "lines": [],
            }
        ],
    }
    with app.test_request_context():
        page = render_template("lesson_body.html", lesson=lesson, csrf="fixture")
    assert "Practice this pin" in page and VERSION in page and "/unified/start" in page


@pytest.mark.parametrize("black", [False, True])
def test_relative_pin_exemplar_proves_actual_legal_defenses(tmp_path, monkeypatch, black):
    db, evidence = owned_pin(
        tmp_path / "relative-proof.sqlite", monkeypatch, black=black, relative=True
    )
    state = begin(db, evidence)
    move = chess.Move.from_uci("a6b5")
    if black:
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    answer = submit(db, "pin", SUBJECT, event_id="answer", move=move.uci())
    assert answer["feedback"] == "needs_verification"
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    board = chess.Board(state["fen"])
    board.push(move)
    assert {branch["reply"] for branch in result["proof"]["branches"]} == {
        reply.uci() for reply in board.legal_moves
    }
    pinned = chess.parse_square(state["pin_pinned"])
    assert any(
        chess.Move.from_uci(branch["reply"]).from_square == pinned
        for branch in result["proof"]["branches"]
    )
    assert result["proof"]["type"] == "relative_pin"


def test_root_capture_remains_unresolved_not_incorrect():
    from chess_coach.objective_pin_judge import verify

    board = chess.Board(ABSOLUTE)
    board.set_piece_at(chess.B7, chess.Piece(chess.ROOK, chess.BLACK))
    move = chess.Move.from_uci("b4b7")
    assert move in board.legal_moves and board.is_capture(move)
    data = {"pin_attacker": "b4", "pin_pinned": "c6", "pin_rear": "c8", "pin_type": "absolute_pin"}
    result = verify(board, move, {"learner_color": "white"}, [], lambda: 0, 0, 5, {}, data)
    assert result["status"] == "unresolved"


def test_harmless_pin_geometry_cannot_become_a_success():
    from chess_coach.objective_pin_judge import verify

    board = chess.Board("4k3/1p6/B1n5/3P4/8/8/8/4K3 w - - 0 1")
    move = chess.Move.from_uci("a6b5")
    binding = {
        "pin_attacker": "a6",
        "pin_pinned": "c6",
        "pin_rear": "e8",
        "pin_type": "absolute_pin",
    }
    result = verify(board, move, {"learner_color": "white"}, [], lambda: 0, 0, 5, {}, binding)
    assert result["status"] == "unresolved"
    assert result["reason"] == "pin_or_consequence_unresolved"
