"""Private evidence, grounded lesson, browser and CLI created-fork practice."""

import json
from argparse import Namespace

from flask import render_template

from chess_coach.cli_related_fork_avoidance import begin, listing
from chess_coach.related_fork_avoidance import preview
from chess_coach.web import create_app
from tests.fork_concealment_support import without_opaque_inputs
from tests.test_fork_defense_pipeline import LEARNER
from tests.test_related_fork_avoidance import created_fixture
from tests.test_unified_sessions import token


def test_cli_conceals_and_starts_created_fork_session(tmp_path, monkeypatch, capsys):
    db, evidence = created_fixture(tmp_path / "cli.sqlite", monkeypatch)
    listing(db, Namespace(subject=LEARNER, evidence=evidence, corpus="test", cursor=None))
    result = json.loads(capsys.readouterr().out)
    assert len(result["items"]) == 1 and "created_witness" not in result["items"][0]
    begin(
        db,
        Namespace(
            subject=LEARNER,
            evidence=evidence,
            corpus="test",
            attempt="cli",
            reference=result["items"][0]["reference"],
        ),
    )
    state = json.loads(capsys.readouterr().out)
    assert state["related_fork_avoidance"] and "source_key" not in state
    db.close()


def test_private_browser_evidence_preview_and_csrf(tmp_path, monkeypatch):
    db_path = tmp_path / "browser.sqlite"
    db, evidence = created_fixture(db_path, monkeypatch)
    reference = preview(db, LEARNER, evidence, "test")["items"][0]["reference"]
    db.close()
    monkeypatch.setattr(
        "chess_coach.web_security.secrets.token_urlsafe",
        lambda size: "A" * (43 if size == 32 else 32),
    )
    app = create_app(
        db_path=db_path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    source = client.get(f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers)
    assert (
        source.status_code == 200 and b"Find practice avoiding a created knight fork" in source.data
    )
    path = f"/evidence/{evidence}/related-fork-avoidances"
    page = client.get(path, base_url="https://coach.invalid", headers=headers)
    with client.session_transaction(base_url="https://coach.invalid") as browser_session:
        csrf = browser_session["csrf"]
    assert page.status_code == 200 and token(page, "reference") == reference
    assert b"across good and bad scans" in page.data
    assert b"b1b3" not in without_opaque_inputs(page.data, csrf, reference)
    data = {"csrf": csrf, "reference": reference}
    assert (
        client.post(
            path + "/start", base_url="https://coach.invalid", headers=headers, data=data
        ).status_code
        == 403
    )
    result = client.post(
        path + "/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=data,
    )
    assert result.status_code == 303
    practice = client.get(
        result.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert practice.status_code == 200 and b"avoids creating" in practice.data
    assert b"b1b3" not in without_opaque_inputs(practice.data, csrf)


def test_grounded_lesson_links_only_created_source(tmp_path):
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
        "created_fork_avoidance": True,
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
        page = render_template("lesson_body.html", lesson=lesson)
        assert "Explore created knight-fork avoidance practice" in page
        example["created_fork_avoidance"] = False
        assert "related-fork-avoidances" not in render_template("lesson_body.html", lesson=lesson)
