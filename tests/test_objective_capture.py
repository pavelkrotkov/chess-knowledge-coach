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
