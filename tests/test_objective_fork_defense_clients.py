"""CLI, evidence, grounded lesson and private browser entry for owned defense."""

import json
import sys

from flask import render_template

from chess_coach.cli import main
from chess_coach.db import Database
from chess_coach.objective_fork_defense_contract import VERSION
from chess_coach.objective_worker import process
from chess_coach.web import create_app
from tests.test_fork_defense_pipeline import LEARNER
from tests.test_objective_fork_defense import fixture


def test_cli_lists_and_starts_owned_defense(tmp_path, monkeypatch, capsys):
    path = tmp_path / "cli.sqlite"
    db, evidence = fixture(path, monkeypatch)
    db.close()
    monkeypatch.setattr(
        sys,
        "argv",
        ["coach", "--db", str(path), "list-fork-defense-practice", "--subject", LEARNER],
    )
    main()
    result = json.loads(capsys.readouterr().out)
    assert result["version"] == VERSION and result["candidates"] == [{"key": str(evidence)}]
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "coach",
            "--db",
            str(path),
            "start-unified",
            "--attempt",
            "cli",
            "--subject",
            LEARNER,
            "--source",
            "own-game",
            "--version",
            VERSION,
            "--key",
            str(evidence),
        ],
    )
    main()
    state = json.loads(capsys.readouterr().out)
    assert state["objective"] == "avoid_anchored_knight_fork" and "a1b1" not in json.dumps(state)


def test_private_evidence_to_queued_result_with_csrf(tmp_path, monkeypatch):
    path = tmp_path / "browser.sqlite"
    db, evidence = fixture(path, monkeypatch)
    db.close()
    monkeypatch.setattr(
        "chess_coach.web_security.secrets.token_urlsafe",
        lambda size: "A" * (43 if size == 32 else 32),
    )
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    evidence_page = client.get(
        f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers
    )
    assert (
        evidence_page.status_code == 200
        and b"Practice this owned fork defense" in evidence_page.data
    )
    with client.session_transaction(base_url="https://coach.invalid") as browser_session:
        csrf = browser_session["csrf"]
    payload = {"csrf": csrf, "source_type": "own-game", "version": VERSION, "key": str(evidence)}
    assert (
        client.post(
            "/unified/start", base_url="https://coach.invalid", headers=headers, data=payload
        ).status_code
        == 403
    )
    accepted = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=payload,
    )
    assert accepted.status_code == 303
    page = client.get(
        accepted.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert page.status_code == 200 and b"Defend against the anchored knight fork" in page.data
    assert b"a1b1" not in page.data
    with client.session_transaction(base_url="https://coach.invalid") as browser_session:
        attempt = browser_session["unified_attempt"]
    result = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={"csrf": csrf, "attempt": attempt, "event": "answer", "move": "a1b1"},
    )
    assert result.status_code == 303
    pending = client.get(
        result.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Verification is queued" in pending.data
    db = Database(path)
    assert process(db, LEARNER)["outcomes"] == {"correct": 1}
    db.close()
    verified = client.get(
        result.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"no supported immediate fork or material threat" in verified.data


def test_grounded_lesson_exposes_owned_defense_form(tmp_path):
    app = create_app(
        db_path=tmp_path / "unused.sqlite",
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    example = {
        "evidence_id": 1,
        "position_id": 1,
        "game_id": 1,
        "ply": 1,
        "review": "unreviewed",
        "played": "move",
        "operation": "prevent",
        "facts": [],
        "lines": [],
        "anchored_fork_prevention": True,
    }
    lesson = {
        "family": "fork-defense-mapper",
        "qualification": "bounded",
        "possible": "possible",
        "question": "question",
        "habit": "habit",
        "practice": "practice",
        "examples": [example],
    }
    with app.test_request_context():
        page = render_template("lesson_body.html", lesson=lesson, csrf="fixture")
        assert "Practice this owned fork defense" in page and VERSION in page
