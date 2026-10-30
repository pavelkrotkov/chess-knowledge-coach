"""Synthetic own-game practice with exact validated material versions."""

import json
from argparse import Namespace

import pytest

from chess_coach import material_policy
from chess_coach.cli_unified_practice import handle_list, handle_show, handle_start
from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.material_detector import process_decision
from chess_coach.unified_own_game import LEGACY_VERSION, VERSION, list_candidates
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


def test_changed_review_and_family_revoke_sessions_without_writes(tmp_path, monkeypatch):
    db, evidence = fixture(tmp_path, monkeypatch)
    key = list_candidates(db, LEARNER)["candidates"][0]["key"]
    begin(db, key)
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    assert list_candidates(db, LEARNER)["candidates"] == []
    for action in (
        lambda: show(db, "a", LEARNER),
        lambda: hint(db, "a", LEARNER, event_id="h"),
        lambda: submit(db, "a", LEARNER, event_id="m", move="d4d5"),
        lambda: begin(db, key),
    ):
        with pytest.raises(ValueError, match="stale"):
            action()
    assert db.connection.execute("SELECT COUNT(*) FROM unified_session_events").fetchone()[0] == 0
    review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
    assert begin(db, key, attempt="accepted")["review_status"] == "accepted"
    monkeypatch.setattr(material_policy, "ELIGIBLE_KINDS", frozenset())
    with pytest.raises(ValueError, match="stale"):
        show(db, "accepted", LEARNER)


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


def test_analysis_change_invalidates_live_session_and_retains_history(tmp_path, monkeypatch):
    db, _ = fixture(tmp_path, monkeypatch)
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


def test_candidate_scan_is_bounded_and_deduplicates(tmp_path, monkeypatch):
    from chess_coach import unified_own_game

    rows = [{"id": n, "position_id": 7} for n in range(1, 102)]
    view = {
        "position_id": 7,
        "objective": {"kind": "material_protection", "target": "d4"},
        "review_status": "unreviewed",
    }
    seen = []
    monkeypatch.setattr(unified_own_game, "_rows", lambda *args: rows)

    def inspect(db, evidence_id, subject, history):
        seen.append(evidence_id)
        return view, None, []

    monkeypatch.setattr(unified_own_game, "_inspect", inspect)
    db = Database(tmp_path / "bounded.sqlite")
    result = list_candidates(db, LEARNER)
    db.close()
    assert len(seen) == 100 and result["scanned"] == 100 and result["truncated"]
    assert result["candidates"] == [
        {
            "key": "7:material_protection:1",
            "objective": "material_protection",
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


def test_validated_black_protection_drill_is_playable(tmp_path, monkeypatch):
    db, _ = fixture(tmp_path, monkeypatch, color="black")
    choices = list_candidates(db, LEARNER)["candidates"]
    assert len(choices) == 1 and choices[0]["objective"] == "material_protection"
    state = begin(db, choices[0]["key"])
    assert state["learner_color"] == "black" and state["review_status"] == "unreviewed"
    assert submit(db, "a", LEARNER, event_id="m", move="d5d4")["status"] == "line_completed"


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


def test_legacy_target_bearing_session_resolves_but_never_echoes_key(tmp_path, monkeypatch):
    db = make_protection_game(tmp_path / "own.sqlite", monkeypatch, played="d4d5")
    process_decision(db, 1, LEARNER)
    key = "1:material_protection:d5"
    initial = start(
        db,
        attempt_id="legacy",
        subject=LEARNER,
        source_type="own-game",
        version=LEGACY_VERSION,
        key=key,
    )
    assert "source_key" not in initial and "objective_target" not in initial
    assert show(db, "legacy", LEARNER) == initial
    assert "source_key" not in recent(db, LEARNER)[0]
    old_response = initial | {
        "source_key": key,
        "objective_target": "d5",
        "feedback": "hint",
        "hint": "d4",
    }
    db.connection.execute(
        "INSERT INTO unified_session_events VALUES(?,?,?,?,?,?)",
        ("legacy", "old-hint", "hint", None, json.dumps(old_response), "2026-01-01"),
    )
    db.connection.commit()
    replay = hint(db, "legacy", LEARNER, event_id="old-hint")
    assert (
        replay["hint"] == "d4" and "source_key" not in replay and "objective_target" not in replay
    )
    stored = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE event_id=?", ("old-hint",)
    ).fetchone()[0]
    assert json.loads(stored)["objective_target"] == "d5"
    assert submit(db, "legacy", LEARNER, event_id="m", move="d4d5")["status"] == "line_completed"


def test_owned_deep_protection_keeps_answer_destination_private(tmp_path, monkeypatch):
    import sys

    import chess
    import chess.engine

    from chess_coach.deep_execution_config import DeepOptions
    from chess_coach.deep_execution_worker import run_deep
    from chess_coach.deep_selection import select_deep
    from chess_coach.material_opportunities import inspect_material_opportunity
    from tests.test_material_pipeline import Engine

    db = make_protection_game(tmp_path / "deep.sqlite", monkeypatch, played="d4d5")
    selected = select_deep(db, [1], learner=LEARNER, per_game=1, total=1)

    class Partial(Engine):
        def analyse(self, board, limit, multipv, root_moves=None):
            root = root_moves[0] if root_moves else chess.Move.from_uci("d4d5")
            info = {
                "pv": [root, chess.Move.from_uci("e8f8")],
                "nodes": 100,
                "depth": 5,
                "time": 0.01,
            }
            if root_moves:
                info["score"] = chess.engine.PovScore(chess.engine.Cp(500), board.turn)
            return [info]

    monkeypatch.setattr(chess.engine.SimpleEngine, "popen_uci", lambda _, timeout: Partial())
    report = run_deep(
        db,
        selected["games"][0]["selection_id"],
        learner=LEARNER,
        options=DeepOptions(engine_path=sys.executable, nodes=1000, seconds=0.5, max_jobs=1),
    )
    assert report["processed"][0]["status"] == "insufficient"
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    detail = inspect_material_opportunity(db, evidence, learner=LEARNER)
    assert detail["lineage"]["analysis"]["kind"] == "deep"
    assert detail["objective"]["target"] == "d5" and detail["objective_witness"]["uci"][0] == "d4d5"
    key = list_candidates(db, LEARNER)["candidates"][0]["key"]
    state = begin(db, key)
    assert state["status"] == "active" and state["hints_used"] == 0
    assert "d5" not in key and "objective_target" not in state and "source_key" not in state


def test_new_keys_resolve_only_newest_eligible_evidence_per_private_objective(monkeypatch):
    from chess_coach import unified_own_game_resolve as resolver

    rows = [{"id": value} for value in (3, 2, 1)]
    views = {
        3: {"position_id": 7, "objective": {"kind": "material_protection", "target": "d4"}},
        2: {"position_id": 7, "objective": {"kind": "material_protection", "target": "d4"}},
        1: {"position_id": 7, "objective": {"kind": "material_protection", "target": "a2"}},
    }
    monkeypatch.setattr(
        resolver, "_inspect", lambda db, evidence, subject: (views[evidence], None, [])
    )
    monkeypatch.setattr(resolver, "snapshot", lambda view, review, evidence: evidence)
    assert resolver._current(None, LEARNER, rows, "material_protection", 3) == 3
    assert resolver._current(None, LEARNER, rows, "material_protection", 1) == 1
    with pytest.raises(ValueError, match="unavailable"):
        resolver._current(None, LEARNER, rows, "material_protection", 2)


def test_reviewed_capture_practice_retains_subject_and_review_gates(tmp_path, monkeypatch):
    db = make_game(tmp_path / "reviewed-capture.sqlite", monkeypatch)
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 30
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    review_evidence(db, evidence, decision="accept", actor="fixture_reviewer")
    choices = list_candidates(db, LEARNER)["candidates"]
    assert len(choices) == 1 and choices[0]["review_status"] == "accepted"
    assert choices[0]["objective"] == "material_capture"
    assert "d1d4" not in json.dumps(choices)
    with pytest.raises(ValueError):
        begin(db, choices[0]["key"], subject="fixture_opponent")
    session = begin(db, choices[0]["key"])
    assert session["review_status"] == "accepted" and "d1d4" not in json.dumps(session)
    assert submit(db, "a", LEARNER, event_id="m", move="d1d4")["status"] == "line_completed"
    review_evidence(db, evidence, decision="revoke", actor="fixture_reviewer")
    assert not list_candidates(db, LEARNER)["candidates"]
    with pytest.raises(ValueError, match="stale"):
        show(db, "a", LEARNER)
