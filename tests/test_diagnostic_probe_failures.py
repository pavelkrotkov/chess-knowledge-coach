"""Probe requests fail closed without creating diagnostic evidence."""

import json

import pytest

from chess_coach.fork_detector import process_decision
from chess_coach.probe_events import event
from chess_coach.probe_sessions import start
from chess_coach.web import create_app
from tests.test_diagnostic_probes import lesson_for
from tests.test_fork_pipeline import LEARNER, make_game


@pytest.fixture
def probe_source(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "probe-errors.sqlite", monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    lesson = lesson_for(db, LEARNER, evidence)
    yield db, lesson, evidence
    db.close()


@pytest.mark.parametrize(
    "event_id,kind,answer",
    [
        ("", "answer", "a8"),
        ("x" * 257, "hint", None),
        ("event", "other", None),
        ("event", "answer", None),
        ("event", "hint", "a8"),
        ("event", "answer", "   "),
        ("event", "answer", "x" * 33),
    ],
)
def test_invalid_events_leave_no_history(probe_source, event_id, kind, answer):
    db, lesson, evidence = probe_source
    start(db, LEARNER, "attempt", lesson, evidence, "recognize")
    with pytest.raises(ValueError):
        event(db, LEARNER, "attempt", event_id, kind, answer)
    assert db.connection.execute("SELECT COUNT(*) FROM diagnostic_probe_events").fetchone()[0] == 0


def test_second_distinct_answer_is_rejected_without_rewriting_first(probe_source):
    db, lesson, evidence = probe_source
    start(db, LEARNER, "attempt", lesson, evidence, "recognize")
    first = event(db, LEARNER, "attempt", "one", "answer", "a8")
    with pytest.raises(ValueError, match="already answered"):
        event(db, LEARNER, "attempt", "two", "answer", "e8")
    assert event(db, LEARNER, "attempt", "one", "answer", "a8") == first
    assert db.connection.execute("SELECT COUNT(*) FROM diagnostic_probe_events").fetchone()[0] == 1


@pytest.mark.parametrize("change", ["missing_example", "changed_example", "wrong_scope"])
def test_changed_saved_lesson_cannot_start_probe(probe_source, change):
    db, lesson_id, evidence = probe_source
    row = db.connection.execute(
        "SELECT lesson_json FROM lesson_versions WHERE id=?", (lesson_id,)
    ).fetchone()
    lesson = json.loads(row[0])
    if change == "missing_example":
        lesson["examples"] = []
    elif change == "changed_example":
        lesson["examples"][0]["position_id"] = -1
    else:
        lesson["skill"] = "different"
    db.connection.execute(
        "UPDATE lesson_versions SET lesson_json=? WHERE id=?", (json.dumps(lesson), lesson_id)
    )
    db.connection.commit()
    with pytest.raises(ValueError):
        start(db, LEARNER, "attempt", lesson_id, evidence, "recognize")
    assert db.connection.execute("SELECT COUNT(*) FROM diagnostic_probes").fetchone()[0] == 0


def test_invalid_attempt_and_existing_transaction_are_rejected(probe_source):
    db, lesson, evidence = probe_source
    for attempt in ("", "x" * 257):
        with pytest.raises(ValueError, match="invalid attempt"):
            start(db, LEARNER, attempt, lesson, evidence, "recognize")
    db.connection.execute(
        "UPDATE lesson_versions SET lesson_json=lesson_json WHERE id=?", (lesson,)
    )
    with pytest.raises(RuntimeError, match="transaction"):
        start(db, LEARNER, "attempt", lesson, evidence, "recognize")
    db.connection.rollback()
    assert db.connection.execute("SELECT COUNT(*) FROM diagnostic_probes").fetchone()[0] == 0


def test_browser_rejects_bad_inputs_and_shows_owned_history(probe_source):
    db, lesson, evidence = probe_source
    path = db.path
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
    headers = {"Tailscale-User-Login": "login", "Origin": "https://coach.invalid"}
    page = client.get(f"/lessons/{lesson}", base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    data = {
        "csrf": csrf,
        "attempt": "browser",
        "lesson": lesson,
        "evidence": evidence,
        "kind": "recognize",
    }
    for invalid in ({"lesson": "bad"}, {"evidence": "bad"}, {"kind": "unsupported"}):
        response = client.post(
            "/probes/start", base_url="https://coach.invalid", headers=headers, data=data | invalid
        )
        assert response.status_code == 400
    response = client.post(
        "/probes/start", base_url="https://coach.invalid", headers=headers, data=data
    )
    assert response.status_code == 303
    assert (
        client.get("/probes/missing", base_url="https://coach.invalid", headers=headers).status_code
        == 404
    )
    assert (
        client.get(
            "/lessons/99999/probes", base_url="https://coach.invalid", headers=headers
        ).status_code
        == 404
    )
    history = client.get(
        f"/lessons/{lesson}/probes", base_url="https://coach.invalid", headers=headers
    )
    assert history.status_code == 200 and b"browser" in history.data
    bad = client.post(
        "/probes/browser/event",
        base_url="https://coach.invalid",
        headers=headers,
        data={"csrf": csrf, "event": "", "kind": "answer", "answer": "a8"},
    )
    assert bad.status_code == 400
