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


def test_unknown_and_reveal_are_not_unaided_evidence(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "probe.sqlite", monkeypatch)
    evidence_id = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    lesson = lesson_for(db, LEARNER, evidence_id)
    start(db, LEARNER, "unknown", lesson, evidence_id, "recognize")
    outcome = event(db, LEARNER, "unknown", "a", "answer", "h7")
    assert outcome["outcome"] == "ungraded" and "blind spot" in outcome["message"]
    assert outcome["evidence"] is None
    start(db, LEARNER, "revealed", lesson, evidence_id, "recognize")
    reveal = event(db, LEARNER, "revealed", "r", "reveal")
    assert reveal == event(db, LEARNER, "revealed", "r", "reveal")
    assert "a8" in reveal["message"]
    outcome = event(db, LEARNER, "revealed", "a", "answer", "a8")
    assert outcome["assisted"] and "after assistance" in outcome["message"]
    assert outcome["evidence"] is None


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


def test_fork_targets_checked_for_both_colors():
    import chess

    from chess_coach.probe_fork import fork

    board = chess.Board("r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1")
    white = fork({"fork_explanation": {"move": "Nc7+", "targets": ["a8", "e8"]}}, board.fen())
    black = fork(
        {"fork_explanation": {"move": "Nc2+", "targets": ["a1", "e1"]}}, board.mirror().fen()
    )
    assert white["accepted"] == ["a8", "e8"]
    assert black["accepted"] == ["a1", "e1"]
    with pytest.raises(ValueError):
        fork({"fork_explanation": {"move": "Nc7+", "targets": ["a8", "h7"]}}, board.fen())


def test_pawn_choice_stays_ungraded_for_unsupported_alternative(tmp_path, monkeypatch):
    import chess

    from chess_coach.pawn_coach_detector import process_decision as pawn_decision
    from chess_coach.pawn_proof import inspect
    from tests.test_mate_proof import owned_game
    from tests.test_pawn_coaching import FEN

    proof = inspect(chess.Board(FEN))
    db = owned_game(tmp_path / "pawn.sqlite", monkeypatch, fen=FEN, move="d4")
    monkeypatch.setattr("chess_coach.pawn_inspection.inspect", lambda board: proof)
    evidence_id = pawn_decision(db, 1, "fixture_a")["evidence_ids"][0]
    row = db.connection.execute(
        "SELECT * FROM evidence_mappings WHERE id=?", (evidence_id,)
    ).fetchone()
    fact = db.connection.execute(
        "SELECT * FROM detector_facts WHERE id=?", (json.loads(row["source_facts_json"])[0],)
    ).fetchone()
    group = {
        "skill": row["skill"],
        "operation": row["operation"],
        "family": "pawn-endgame-mapper",
        "version": fact["detector_version"],
        "lesson_examples": [{"id": evidence_id, "position_id": 1, "context": {}}],
    }
    lesson = save(db, "fixture_a", build(db, "fixture_a", group))
    db.connection.commit()
    state = start(db, "fixture_a", "pawn", lesson, evidence_id, "evaluate")
    assert state["operation"] == "evaluate" and "accepted" not in json.dumps(state)
    result = event(db, "fixture_a", "pawn", "answer", "answer", "Kf4")
    assert result["outcome"] == "ungraded" and "blind spot" in result["message"]
    start(db, "fixture_a", "pawn2", lesson, evidence_id, "evaluate")
    result = event(db, "fixture_a", "pawn2", "answer", "answer", "Ke4")
    assert result["outcome"] == "supported" and result["operation"] == "evaluate"


def test_revocation_prevents_start_and_new_events_preserving_history(tmp_path, monkeypatch):
    from chess_coach.evidence_review import review_evidence

    db, _ = make_game(tmp_path / "revoked.sqlite", monkeypatch)
    evidence_id = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    lesson = lesson_for(db, LEARNER, evidence_id)
    start(db, LEARNER, "prior", lesson, evidence_id, "recognize")
    hint = event(db, LEARNER, "prior", "h", "hint")
    assert hint == event(db, LEARNER, "prior", "h", "hint")
    review_evidence(db, evidence_id, decision="reject", actor="fixture")
    with pytest.raises(ValueError):
        start(db, LEARNER, "new", lesson, evidence_id, "recognize")
    with pytest.raises(ValueError):
        event(db, LEARNER, "prior", "a", "answer", "a8")
    historical = show(db, LEARNER, "prior")
    assert historical["stale"] and historical["events"] == [hint]
    assert db.connection.execute("SELECT COUNT(*) FROM diagnostic_probes").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM diagnostic_probe_events").fetchone()[0] == 1
    with pytest.raises(Exception, match="immutable"):
        db.connection.execute("DELETE FROM diagnostic_probe_events")


def test_changed_lesson_version_cannot_admit_new_task(tmp_path, monkeypatch):
    db, _ = make_game(tmp_path / "changed.sqlite", monkeypatch)
    evidence_id = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    lesson_id = lesson_for(db, LEARNER, evidence_id)
    stored = db.connection.execute(
        "SELECT lesson_json FROM lesson_versions WHERE id=?", (lesson_id,)
    ).fetchone()
    lesson = json.loads(stored["lesson_json"])
    lesson["source_version"] = "different"
    db.connection.execute(
        "UPDATE lesson_versions SET lesson_json=? WHERE id=?", (json.dumps(lesson), lesson_id)
    )
    db.connection.commit()
    with pytest.raises(ValueError, match="version"):
        start(db, LEARNER, "changed", lesson_id, evidence_id, "recognize")
    assert db.connection.execute("SELECT COUNT(*) FROM diagnostic_probes").fetchone()[0] == 0


def test_mate_probe_requires_cited_proof_and_checks_both_colors():
    import chess

    from chess_coach.probe_mate import mate
    from tests.test_mate_proof import FEN

    board = chess.Board(FEN)
    for position in (board, board.mirror()):
        move = next(move for move in position.legal_moves if position.gives_check(move))
        san = position.san(move)
        evidence = {
            "facts": [
                {
                    "payload": {
                        "proof": {"alternatives": [{"status": "proved", "move": {"san": san}}]}
                    }
                }
            ]
        }
        task = mate(evidence, position.fen())
        after = position.copy()
        after.push(move)
        assert set(task["accepted"]) == {chess.square_name(s) for s in after.checkers()}
        evidence["facts"][0]["payload"]["proof"]["alternatives"][0]["status"] = "unproved"
        with pytest.raises(ValueError):
            mate(evidence, position.fen())


def test_review_revocation_and_malformed_lesson_fail_closed(tmp_path, monkeypatch):
    from chess_coach.evidence_review import review_evidence

    db, _ = make_game(tmp_path / "revocation.sqlite", monkeypatch)
    evidence_id = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    review_evidence(db, evidence_id, decision="accept", actor="fixture")
    lesson = lesson_for(db, LEARNER, evidence_id)
    start(db, LEARNER, "before", lesson, evidence_id, "recognize")
    review_evidence(db, evidence_id, decision="revoke", actor="fixture")
    with pytest.raises(ValueError):
        event(db, LEARNER, "before", "a", "answer", "a8")
    with pytest.raises(ValueError):
        start(db, LEARNER, "after", lesson, evidence_id, "recognize")
    assert db.connection.execute("SELECT COUNT(*) FROM diagnostic_probe_events").fetchone()[0] == 0
    db.connection.execute("UPDATE lesson_versions SET lesson_json=? WHERE id=?", ("{}", lesson))
    db.connection.commit()
    with pytest.raises(ValueError):
        start(db, LEARNER, "bad", lesson, evidence_id, "recognize")
