"""Synthetic own-game practice with exact validated material versions."""

import json
from argparse import Namespace

import pytest

from chess_coach.cli_unified_practice import handle_list, handle_show, handle_start
from chess_coach.db import Database
from chess_coach.material_detector import process_decision
from chess_coach.unified_own_game import VERSION, list_candidates
from chess_coach.unified_session_events import hint, show, submit
from chess_coach.unified_session_state import recent
from chess_coach.unified_sessions import start
from chess_coach.web import create_app
from tests.test_material_pipeline import LEARNER, make_game, make_protection_game
from tests.test_unified_sessions import token


def fixture(tmp_path, monkeypatch, *, color="white"):
    db = make_protection_game(tmp_path / "own.sqlite", monkeypatch, color=color)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    return db, evidence


def begin(db, key, subject=LEARNER, attempt="a"):
    return start(
        db, attempt_id=attempt, subject=subject, source_type="own-game", version=VERSION, key=key
    )


def test_capture_gate_and_unreviewed_protection_practice(tmp_path, monkeypatch, capsys):
    from chess_coach import material_contract

    capture = make_game(tmp_path / "capture.sqlite", monkeypatch)
    monkeypatch.setattr(material_contract, "CAPTURE_VERSION", "1.0.0")
    process_decision(capture, 1, LEARNER)
    monkeypatch.setattr(material_contract, "CAPTURE_VERSION", "1.1.0")
    closed = list_candidates(capture, LEARNER)
    assert closed["candidates"] == []
    assert closed["excluded"]["detector family not independently validated"] == 1
    with pytest.raises(ValueError):
        begin(capture, "1:material_capture:d4")
    db, evidence = fixture(tmp_path, monkeypatch)
    ready = list_candidates(db, LEARNER)
    assert ready["scanned"] == 1 and len(ready["candidates"]) == 1
    item = ready["candidates"][0]
    assert item["review_status"] == "unreviewed"
    assert "d4d5" not in json.dumps(ready)
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
    assert shown["review_status"] == "unreviewed" and "d4d5" not in json.dumps(shown)
    state = begin(db, item["key"])
    assert state["learner_color"] == "white" and state["review_status"] == "unreviewed"
    assert submit(db, "a", LEARNER, event_id="m", move="d4d5")["status"] == "line_completed"
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    assert evidence > 0


def test_private_browser_own_game_and_unlisted_move(tmp_path, monkeypatch):
    db, _ = fixture(tmp_path, monkeypatch)
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
        library.status_code == 200
        and b"provisional" in library.data
        and b"d4d5" not in library.data
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
        and b"d4d5" not in page.data
    )
    posted = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "attempt": token(page, "attempt"),
            "event": token(page, "event"),
            "move": "a2a3",
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
    assert b"Target square:" not in page.data and b"View source evidence" not in page.data
    posted = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "attempt": token(page, "attempt"),
            "event": token(page, "event"),
            "move": "d4d5",
        },
    )
    page = client.get(posted.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert b"Line complete" in page.data and b"Checkmate verified" not in page.data
    assert b"View source evidence" in page.data


def test_own_game_session_survives_reopen_without_learning_writes(tmp_path, monkeypatch):
    db, _ = fixture(tmp_path, monkeypatch)
    tables = (
        "evidence_mappings",
        "mastery_events",
        "mastery_states",
        "training_items",
        "training_attempts",
    )
    before = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }
    key = list_candidates(db, LEARNER)["candidates"][0]["key"]
    initial = begin(db, key)
    clue = hint(db, "a", LEARNER, event_id="h")
    db.close()
    db = Database(tmp_path / "own.sqlite")
    assert show(db, "a", LEARNER)["fen"] == initial["fen"]
    assert hint(db, "a", LEARNER, event_id="h") == clue
    assert submit(db, "a", LEARNER, event_id="m", move="d4d5")["status"] == "line_completed"
    after = {
        table: db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in tables
    }
    assert after == before
    db.close()


@pytest.mark.parametrize(
    "color,move,destination", [("white", "d4d5", "d5"), ("black", "d5d4", "d4")]
)
def test_successful_protection_never_exposes_answer_destination_before_hint(
    tmp_path, monkeypatch, capsys, color, move, destination
):
    import chess

    from chess_coach.material_opportunities import inspect_material_opportunity

    db = make_protection_game(tmp_path / "own.sqlite", monkeypatch, played="d4d5", color=color)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    detail = inspect_material_opportunity(db, evidence, learner=LEARNER)
    assert detail["outcome"] == "success" and detail["objective"]["target"] == destination
    assert detail["objective_witness"]["uci"][0] == move
    assert chess.Board(detail["decision_fen"]).piece_at(chess.parse_square(destination)) is None
    candidates = list_candidates(db, LEARNER)["candidates"]
    assert len(candidates) == 1 and candidates[0]["key"].split(":")[-1] == str(evidence)
    assert destination not in candidates[0]["key"]
    state = begin(db, candidates[0]["key"])
    assert state["hints_used"] == 0 and state["status"] == "active"
    assert "objective_target" not in state and "source_key" not in state
    row = db.connection.execute(
        "SELECT provenance_json,lines_json FROM unified_sessions WHERE attempt_id=?", ("a",)
    ).fetchone()
    assert json.loads(row["provenance_json"])["objective_target"] == destination
    assert json.loads(row["lines_json"])[0][0] == move
    assert "source_key" not in recent(db, LEARNER)[0]
    capsys.readouterr()
    handle_list(db, Namespace(subject=LEARNER))
    listed = json.loads(capsys.readouterr().out)["candidates"]
    assert listed[0]["key"].split(":")[-1] == str(evidence)
    handle_start(
        db,
        Namespace(
            attempt="cli",
            subject=LEARNER,
            source="own-game",
            version=VERSION,
            key=candidates[0]["key"],
        ),
    )
    cli_start = json.loads(capsys.readouterr().out)
    assert "source_key" not in cli_start and "objective_target" not in cli_start
    handle_show(db, Namespace(attempt="cli", subject=LEARNER))
    cli_show = json.loads(capsys.readouterr().out)
    assert "source_key" not in cli_show and "objective_target" not in cli_show
    assert all("source_key" not in item for item in recent(db, LEARNER))
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
    body = library.get_data(as_text=True)
    assert f"material_protection:{destination}" not in body
    assert token(library, "key").split(":")[-1] == str(evidence)
    response = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": token(library, "csrf"),
            "source_type": "own-game",
            "version": VERSION,
            "key": candidates[0]["key"],
        },
    )
    assert response.status_code == 303
    page = client.get(
        response.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert (
        page.status_code == 200
        and b"Target square:" not in page.data
        and move.encode() not in page.data
    )
