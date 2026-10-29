"""Synthetic, explicitly promoted fixtures for conditional own-game practice."""

import json
from argparse import Namespace

import pytest

from chess_coach import material_opportunity_view
from chess_coach.cli_unified_practice import handle_list, handle_start
from chess_coach.evidence_review import review_evidence
from chess_coach.material_detector import process_decision
from chess_coach.unified_own_game import VERSION, list_candidates
from chess_coach.unified_session_events import hint, show, submit
from chess_coach.unified_sessions import start
from chess_coach.web import create_app
from tests.test_material_pipeline import LEARNER, make_game
from tests.test_unified_sessions import token


def fixture(tmp_path, monkeypatch):
    db = make_game(tmp_path / "own.sqlite", monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    return db, evidence


def approve_family(monkeypatch):
    # Explicitly synthetic only; the real family promotion set remains empty.
    monkeypatch.setattr(
        material_opportunity_view, "MASTERY_ELIGIBLE_VERSIONS", frozenset({"1.0.0"})
    )


def begin(db, key, subject=LEARNER, attempt="a"):
    return start(
        db, attempt_id=attempt, subject=subject, source_type="own-game", version=VERSION, key=key
    )


def test_closed_gate_and_unreviewed_synthetic_practice(tmp_path, monkeypatch, capsys):
    db, evidence = fixture(tmp_path, monkeypatch)
    closed = list_candidates(db, LEARNER)
    assert closed["candidates"] == []
    assert closed["excluded"]["detector family not independently validated"] == 1
    with pytest.raises(ValueError):
        begin(db, "1:material_capture:d4")
    approve_family(monkeypatch)
    ready = list_candidates(db, LEARNER)
    assert ready["scanned"] == 1 and len(ready["candidates"]) == 1
    item = ready["candidates"][0]
    assert item["review_status"] == "unreviewed"
    assert "d1d4" not in json.dumps(ready)
    assert list_candidates(db, "different")["candidates"] == []
    with pytest.raises(ValueError):
        begin(db, item["key"], subject="different")
    handle_list(db, Namespace(subject=LEARNER))
    assert json.loads(capsys.readouterr().out)["candidates"] == ready["candidates"]
    handle_start(
        db,
        Namespace(
            attempt="cli", subject=LEARNER, source="own-game", version=VERSION, key=item["key"]
        ),
    )
    shown = json.loads(capsys.readouterr().out)
    assert shown["review_status"] == "unreviewed" and "d1d4" not in json.dumps(shown)
    state = begin(db, item["key"])
    assert state["learner_color"] == "white" and state["review_status"] == "unreviewed"
    assert submit(db, "a", LEARNER, event_id="m", move="d1d4")["status"] == "line_completed"
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    assert evidence > 0


def test_changed_review_and_family_revoke_sessions_without_writes(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path, monkeypatch)
    approve_family(monkeypatch)
    key = list_candidates(db, LEARNER)["candidates"][0]["key"]
    begin(db, key)
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    assert list_candidates(db, LEARNER)["candidates"] == []
    for action in (
        lambda: show(db, "a", LEARNER),
        lambda: hint(db, "a", LEARNER, event_id="h"),
        lambda: submit(db, "a", LEARNER, event_id="m", move="d1d4"),
        lambda: begin(db, key),
    ):
        with pytest.raises(ValueError, match="stale"):
            action()
    assert db.connection.execute("SELECT COUNT(*) FROM unified_session_events").fetchone()[0] == 0
    review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
    assert begin(db, key, attempt="accepted")["review_status"] == "accepted"
    monkeypatch.setattr(material_opportunity_view, "MASTERY_ELIGIBLE_VERSIONS", frozenset())
    with pytest.raises(ValueError, match="stale"):
        show(db, "accepted", LEARNER)


def test_private_browser_own_game_and_unlisted_move(tmp_path, monkeypatch):
    db, _ = fixture(tmp_path, monkeypatch)
    approve_family(monkeypatch)
    key = list_candidates(db, LEARNER)["candidates"][0]["key"]
    db.close()
    app = create_app(
        db_path=tmp_path / "own.sqlite",
        subject=LEARNER,
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert (
        library.status_code == 200 and b"unreviewed" in library.data and b"d1d4" not in library.data
    )
    csrf = token(library, "csrf")
    posted = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={"csrf": csrf, "source_type": "own-game", "version": VERSION, "key": key},
    )
    assert posted.status_code == 303
    page = client.get(posted.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert (
        b"provisional" in page.data
        and b"learner plays white at the bottom" in page.data
        and b"d1d4" not in page.data
    )
    posted = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "attempt": token(page, "attempt"),
            "event": token(page, "event"),
            "move": "e1f1",
        },
    )
    page = client.get(posted.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert b"needs verification" in page.data

    rejected = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={"source_type": "own-game", "version": VERSION, "key": key},
    )
    assert rejected.status_code == 403
    posted = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={"csrf": csrf, "source_type": "own-game", "version": VERSION, "key": key},
    )
    page = client.get(posted.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert b"Target square: d4" in page.data and b"View source evidence" in page.data
    posted = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "attempt": token(page, "attempt"),
            "event": token(page, "event"),
            "move": "d1d4",
        },
    )
    page = client.get(posted.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert b"line_completed" in page.data and b"objective_verified" not in page.data


def test_analysis_change_invalidates_live_session_and_retains_history(tmp_path, monkeypatch):
    db, _ = fixture(tmp_path, monkeypatch)
    approve_family(monkeypatch)
    key = list_candidates(db, LEARNER)["candidates"][0]["key"]
    begin(db, key)
    hint(db, "a", LEARNER, event_id="h")
    db.connection.execute(
        "UPDATE decision_analysis_lines SET score_value=score_value+1 WHERE position_id=1 AND role=?",
        ("best",),
    )
    db.connection.commit()
    assert list_candidates(db, LEARNER)["candidates"] == []
    with pytest.raises(ValueError, match="stale"):
        show(db, "a", LEARNER)
    assert db.connection.execute("SELECT COUNT(*) FROM unified_session_events").fetchone()[0] == 1


def test_candidate_scan_is_bounded_and_deduplicates(monkeypatch):
    from chess_coach import unified_own_game

    rows = [{"id": n} for n in range(101)]
    view = {
        "position_id": 7,
        "objective": {"kind": "material_capture", "target": "d4"},
        "review_status": "unreviewed",
    }
    seen = []
    monkeypatch.setattr(unified_own_game, "_rows", lambda *args: rows)

    def inspect(db, evidence_id, subject):
        seen.append(evidence_id)
        return view, None, []

    monkeypatch.setattr(unified_own_game, "_inspect", inspect)
    result = list_candidates(None, LEARNER)
    assert len(seen) == 100 and result["scanned"] == 100 and result["truncated"]
    assert result["candidates"] == [
        {
            "key": "7:material_capture:d4",
            "objective": "material_capture",
            "review_status": "unreviewed",
        }
    ]


def test_black_synthetic_witness_preserves_turn_and_rejects_wrong_color():
    import chess

    from chess_coach.unified_own_game_snapshot import snapshot

    board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1").mirror()
    view = {
        "decision_fen": board.fen(),
        "learner_color": "black",
        "position_id": 7,
        "objective": {"kind": "material_capture", "target": "d5"},
        "objective_witness": {"uci": ["d8d5"], "role": "best"},
        "lineage": {},
        "source_fingerprint": "synthetic",
        "review_status": "unreviewed",
    }
    result = snapshot(view, None, 8)
    assert result["learner_color"] == "black" and result["lines"] == ["d8d5"]
    view["learner_color"] = "white"
    with pytest.raises(ValueError, match="witness"):
        snapshot(view, None, 8)
