"""Private evidence, lesson, browser and CLI access for anchored defense."""

import json
from argparse import Namespace

from flask import render_template

from chess_coach.cli_related_fork_prevention import begin, listing
from chess_coach.related_fork_prevention import preview
from chess_coach.web import create_app
from tests.fork_concealment_support import without_opaque_inputs
from tests.test_fork_defense_pipeline import LEARNER
from tests.test_related_fork_prevention import source_and_corpus
from tests.test_unified_sessions import token


def test_cli_lists_and_starts_the_concealed_defense(tmp_path, monkeypatch, capsys):
    db, evidence = source_and_corpus(tmp_path / "cli.sqlite", monkeypatch)
    listing(db, Namespace(subject=LEARNER, evidence=evidence, corpus="test", cursor=None))
    result = json.loads(capsys.readouterr().out)
    assert len(result["items"]) == 1 and "matching_lines" not in result["items"][0]
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
    assert state["related_fork_prevention"] and "source_key" not in state
    db.close()


def test_private_evidence_preview_csrf_and_session(tmp_path, monkeypatch):
    path = tmp_path / "browser.sqlite"
    db, evidence = source_and_corpus(path, monkeypatch)
    reference = preview(db, LEARNER, evidence, "test")["items"][0]["reference"]
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
    source = client.get(f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers)
    assert (
        source.status_code == 200 and b"Find anchored knight-fork defense practice" in source.data
    )
    path = f"/evidence/{evidence}/related-fork-preventions"
    page = client.get(path, base_url="https://coach.invalid", headers=headers)
    with client.session_transaction(base_url="https://coach.invalid") as browser_session:
        csrf = browser_session["csrf"]
    assert page.status_code == 200 and token(page, "reference") == reference
    assert b"a1b1" not in without_opaque_inputs(page.data, csrf, reference)
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
    assert practice.status_code == 200 and b"pre-existing knight-fork threat" in practice.data
    assert b"a1b1" not in without_opaque_inputs(practice.data, csrf)


def test_grounded_lesson_links_only_anchored_source(tmp_path):
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
        page = render_template("lesson_body.html", lesson=lesson)
        assert "Explore anchored knight-fork defense practice" in page
        example["anchored_fork_prevention"] = False
        page = render_template("lesson_body.html", lesson=lesson)
        assert "related-fork-preventions" not in page
