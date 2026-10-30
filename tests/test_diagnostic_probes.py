"""Cued probes preserve source lineage, events and causal uncertainty."""

import json

import pytest

from chess_coach.fork_detector import process_decision
from chess_coach.lesson_history import save
from chess_coach.lesson_narrative import build
from chess_coach.probe_events import event
from chess_coach.probe_sessions import start
from chess_coach.probe_views import show
from tests.test_fork_pipeline import LEARNER, make_game


def lesson_for(db, subject, evidence_id):
    row = db.connection.execute(
        "SELECT * FROM evidence_mappings WHERE id=?", (evidence_id,)
    ).fetchone()
    fact_id = json.loads(row["source_facts_json"])[0]
    fact = db.connection.execute("SELECT * FROM detector_facts WHERE id=?", (fact_id,)).fetchone()
    group = {
        "skill": row["skill"],
        "operation": row["operation"],
        "family": "fork-opportunity-mapper",
        "version": fact["detector_version"],
        "lesson_examples": [{"id": evidence_id, "position_id": 1, "context": {}}],
    }
    lesson = build(db, subject, group)
    assert lesson["examples"]
    result = save(db, subject, lesson)
    db.connection.commit()
    return result


def test_fork_probe_events_are_private_replayable_and_cued(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "probe.sqlite", monkeypatch)
    result = process_decision(db, 1, LEARNER)
    evidence_id = result["evidence_ids"][0]
    lesson = lesson_for(db, LEARNER, evidence_id)
    tables = (
        "evidence_mappings",
        "evidence_review_events",
        "training_attempts",
        "mastery_states",
        "mastery_events",
    )
    before = [
        db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables
    ]
    state = start(db, LEARNER, "attempt", lesson, evidence_id, "recognize")
    assert state["familiarity"] == "cued and familiar"
    assert "accepted" not in json.dumps(state)
    assert start(db, LEARNER, "attempt", lesson, evidence_id, "recognize") == state
    with pytest.raises(ValueError):
        show(db, "other", "attempt")
    response = event(db, LEARNER, "attempt", "answer", "answer", "a8")
    assert response["outcome"] == "supported" and response["operation"] == "recognize"
    assert response["evidence"]["qualification"] == "cued and familiar"
    assert "cannot" in response["message"] and response["elapsed_seconds"] >= 0
    assert response == event(db, LEARNER, "attempt", "answer", "answer", "a8")
    with pytest.raises(ValueError):
        event(db, LEARNER, "attempt", "answer", "answer", "e8")
    assert db.connection.execute("SELECT COUNT(*) FROM diagnostic_probe_events").fetchone()[0] == 1
    assert [
        db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables
    ] == before
    db.connection.execute(
        "UPDATE detector_runs SET status='superseded' WHERE id=?", (result["detector_run_id"],)
    )
    db.connection.commit()
    with pytest.raises(ValueError):
        event(db, LEARNER, "attempt", "next", "reveal")


def test_browser_probe_requires_action_to_reveal(tmp_path, monkeypatch):
    from chess_coach.web import create_app

    path = tmp_path / "browser.sqlite"
    db, _ = make_game(path, monkeypatch)
    evidence_id = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    lesson = lesson_for(db, LEARNER, evidence_id)
    db.close()
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="fixture",
        login="login",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "login"}
    page = client.get(f"/lessons/{lesson}", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200 and b"Try a short probe" in page.data
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    headers["Origin"] = "https://coach.invalid"
    started = client.post(
        "/probes/start",
        base_url="https://coach.invalid",
        headers=headers,
        data={
            "csrf": csrf,
            "attempt": "browser",
            "lesson": lesson,
            "evidence": evidence_id,
            "kind": "recognize",
        },
    )
    assert started.status_code == 303
    page = client.get(started.location, base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200 and b"cued, familiar" in page.data
    assert b"Accepted answers:" not in page.data
    answered = client.post(
        "/probes/browser/event",
        base_url="https://coach.invalid",
        headers=headers,
        data={"csrf": csrf, "event": "a", "kind": "answer", "answer": "a8"},
    )
    assert answered.status_code == 303
    page = client.get(answered.location, base_url="https://coach.invalid", headers=headers)
    assert b"matches the cited proof" in page.data and b"cannot establish" in page.data
