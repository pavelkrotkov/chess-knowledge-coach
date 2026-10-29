"""Synthetic bounded capture objectives preserve source and event history."""

import json

import chess
import pytest

from chess_coach.evidence_review import review_evidence
from chess_coach.material_detector import process_decision
from chess_coach.objective_capture_contract import GAIN_VERSION, TARGET_VERSION
from chess_coach.objective_capture_judge import judge
from chess_coach.objective_status import inspect
from chess_coach.objective_worker import process
from chess_coach.unified_session_events import show, submit
from chess_coach.unified_sessions import start
from tests.test_material_pipeline import LEARNER, make_game


def evaluate(board, move, objective="capture_named_target", target="d4"):
    return judge(
        board,
        board.parse_uci(move),
        objective,
        chess.parse_square(target),
        3,
        lambda: 0.0,
        0.0,
        5.0,
        {},
    )


@pytest.mark.parametrize("black", [False, True])
def test_equivalent_captures_and_named_target(black):
    board = chess.Board("4k3/8/8/8/R2q4/8/8/3RK3 w - - 0 1")
    if black:
        board = board.mirror()
    moves = ("a5d5", "d8d5", "e8f8") if black else ("a4d4", "d1d4", "e1f1")
    target = "d5" if black else "d4"
    for move in moves[:2]:
        result = evaluate(board, move, target=target)
        assert (
            result["status"] == "correct"
            and result["proven_gain_floor"] == 3
            and result["exchange_gain"] == 9
        )
        assert result["legal_replies"]
        assert evaluate(board, move, "bounded_material_gain", target)["status"] == "correct"
    assert evaluate(board, moves[2], target=target)["reason"] == "named_target_not_captured"
    assert evaluate(board, moves[2], "bounded_material_gain", target)["status"] == "unresolved"


def test_gain_floor_is_not_the_target_exchange_value():
    from chess_coach.material_lines import material

    board = chess.Board("4k3/8/5n2/7R/3q4/8/8/3RK3 w - - 0 1")
    initial = material(board, chess.WHITE)
    result = evaluate(board, "d1d4", "bounded_material_gain")
    assert result["status"] == "correct"
    assert result["exchange_gain"] == 9 and result["proven_gain_floor"] == 3
    assert "f6h5" in result["legal_replies"] and "minimum_gain" not in result
    board.push_uci("d1d4")
    board.push_uci("f6h5")
    assert material(board, chess.WHITE) - initial == 4


def test_checks_recaptures_and_history_are_unresolved():
    board = chess.Board("4k3/8/8/3r4/3q4/8/8/3RK3 w - - 0 1")
    assert evaluate(board, "d1d4")["status"] == "unresolved"
    checking = chess.Board("4k3/4q3/8/8/8/8/4R3/6K1 w - - 0 1")
    assert evaluate(checking, "e2e7", target="e7")["reason"] == "checking_or_special_move"
    board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    result = judge(
        board,
        board.parse_uci("d1d4"),
        "bounded_material_gain",
        chess.D4,
        3,
        lambda: 10.0,
        0.0,
        5.0,
        {},
    )
    assert result["reason"] == "timeout"


@pytest.mark.parametrize("version", [TARGET_VERSION, GAIN_VERSION])
def test_owned_session_immutable_retry_and_stale_review(tmp_path, monkeypatch, version):
    db = make_game(tmp_path / "capture.sqlite", monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    state = start(
        db,
        attempt_id="one",
        subject=LEARNER,
        source_type="own-game",
        version=version,
        key=str(evidence),
    )
    assert state["gain_threshold"] == 3
    if version == TARGET_VERSION:
        assert state["objective_target"] == "d4"
    else:
        assert "objective_target" not in state
    before = db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0]
    response = submit(db, "one", LEARNER, event_id="move", move="e1f1")
    assert response["feedback"] == "needs_verification"
    frozen = db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
    assert process(db, LEARNER)["processed"] == 1
    outcome = inspect(db, LEARNER, "one", "move")
    assert outcome["status"] == ("incorrect" if version == TARGET_VERSION else "unresolved")
    assert submit(db, "one", LEARNER, event_id="move", move="e1f1") == response
    assert (
        db.connection.execute("SELECT response_json FROM unified_session_events").fetchone()[0]
        == frozen
    )
    assert db.connection.execute("SELECT COUNT(*) FROM mastery_events").fetchone()[0] == before
    assert show(db, "one", LEARNER)["verification"]["status"] == outcome["status"]
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    with pytest.raises(ValueError):
        show(db, "one", LEARNER)
    assert json.loads(frozen)["feedback"] == "needs_verification"


def test_review_change_between_compute_and_publication_is_unresolved(tmp_path, monkeypatch):
    from chess_coach.objective_verify import compute

    db = make_game(tmp_path / "race.sqlite", monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    start(
        db,
        attempt_id="race",
        subject=LEARNER,
        source_type="own-game",
        version=TARGET_VERSION,
        key=str(evidence),
    )
    submit(db, "race", LEARNER, event_id="move", move="e1f1")

    def change_review(database, request, clock, *, seconds):
        result = compute(database, request, clock, seconds=seconds)
        assert result["status"] == "incorrect"
        review_evidence(database, evidence, decision="reject", actor="fixture_reviewer")
        return result

    assert process(db, LEARNER, verifier=change_review)["outcomes"] == {"unresolved": 1}
    result = json.loads(
        db.connection.execute("SELECT result_json FROM objective_results").fetchone()[0]
    )
    assert result["reason"] == "source_unavailable" and result["learning_eligible"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("producer", "other"),
        ("mapper_version", "other"),
        ("subject", "other"),
        ("operation", "prevent"),
        ("scope_key", "other"),
        ("status", "superseded"),
    ],
)
def test_changed_mapping_identity_refuses_owned_source(tmp_path, monkeypatch, field, value):
    db = make_game(tmp_path / "identity.sqlite", monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    run = db.connection.execute(
        "SELECT mapping_run_id FROM evidence_mappings WHERE id=?", (evidence,)
    ).fetchone()[0]
    db.connection.execute(f"UPDATE mapping_runs SET {field}=? WHERE id=?", (value, run))
    db.connection.commit()
    with pytest.raises(ValueError):
        start(
            db,
            attempt_id="changed",
            subject=LEARNER,
            source_type="own-game",
            version=TARGET_VERSION,
            key=str(evidence),
        )


def test_browser_and_cli_resume_show_the_bound_objective(tmp_path, monkeypatch, capsys):
    from argparse import Namespace

    from chess_coach.cli_unified_practice import handle_show, handle_start
    from chess_coach.web import create_app
    from tests.test_unified_sessions import token

    path = tmp_path / "browser.sqlite"
    db = make_game(path, monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    handle_start(
        db,
        Namespace(
            attempt="cli",
            subject=LEARNER,
            source="own-game",
            version=TARGET_VERSION,
            key=str(evidence),
        ),
    )
    assert json.loads(capsys.readouterr().out)["objective_target"] == "d4"
    handle_show(db, Namespace(attempt="cli", subject=LEARNER))
    assert json.loads(capsys.readouterr().out)["gain_threshold"] == 3
    db.close()
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert library.status_code == 200 and b"Capture the named target" in library.data
    post = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(library, "csrf"),
            "source_type": "own-game",
            "version": TARGET_VERSION,
            "key": str(evidence),
        },
    )
    assert post.status_code == 303
    page = client.get(post.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert b"Capture the piece on d4" in page.data and b"at least 3 material points" in page.data
    move = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(page, "csrf"),
            "attempt": token(page, "attempt"),
            "event": token(page, "event"),
            "move": "e1f1",
        },
    )
    assert move.status_code == 303
    pending = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Verification is queued" in pending.data
    from chess_coach.db import Database

    db = Database(path)
    assert process(db, LEARNER)["outcomes"] == {"incorrect": 1}
    db.close()
    resumed = client.get(
        move.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"This move did not capture the named target" in resumed.data
