"""Licensed direct-prompt material remains explicit, bounded and immutable."""

import csv
import hashlib
import json
import re
import sqlite3

import chess
import pytest

from chess_coach.db import Database
from chess_coach.public_training import import_collection
from chess_coach.public_training_query import collections, tasks
from chess_coach.public_training_query import task as get_task
from chess_coach.web import create_app

MATE = "7k/8/6K1/2Q5/8/8/8/8 w - - 1 2"


def file_set(root, *, rows=None, license="CC0-1.0", fmt="fen_csv", text=None):
    source = root / "collection.data"
    if text is None:
        with source.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["id", "fen", "objective", "lines"])
            for row in rows or []:
                writer.writerow([row[0], row[1], row[2], json.dumps(row[3])])
    else:
        source.write_text(text)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    manifest = {
        "version": "fixture",
        "source_url": "https://example.invalid/source",
        "source_revision": "v1",
        "source_sha256": digest,
        "content_sha256": digest,
        "content_format": fmt,
        "license": license,
        "attribution": "Fixture author",
        "license_notice": "CC0 1.0 https://creativecommons.org/publicdomain/zero/1.0/",
    }
    file = root / "manifest.json"
    file.write_text(json.dumps(manifest))
    return source, file, manifest


def test_direct_prompt_alternatives_exclusions_export_and_private_view(
    tmp_path, monkeypatch, capsys
):
    from chess_coach.public_mate_contract import OBJECTIVE

    white = chess.Board(MATE.replace(" 1 2", " 0 2"))
    black = white.mirror()
    rows = [
        ("mate", MATE, "checkmate", ["c5f8", "c5c8"]),
        ("white-m1", white.fen(), OBJECTIVE, ["c5f8"]),
        ("black-m1", black.fen(), OBJECTIVE, ["c4f1"]),
        ("clock-unknown", MATE, OBJECTIVE, ["c5f8"]),
        ("multi-ply", chess.STARTING_FEN, OBJECTIVE, ["e2e4 e7e5"]),
        ("bad", MATE, "checkmate", ["c5b5"]),
        ("unknown", MATE, "unverified_source", ["c5f8"]),
    ]
    path, manifest, metadata = file_set(tmp_path, rows=rows)
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    result = import_collection(db, path, path, manifest, project_root=tmp_path)
    assert result == {"version": "fixture", "accepted": 3, "excluded": 4}
    assert len(tasks(db, "fixture")) == 3
    task = get_task(db, "fixture", "mate")
    assert task["prompt_fen"] == MATE
    assert task["lines"] == ["c5f8", "c5c8"]
    assert task["attribution"] == metadata["attribution"]
    assert task["license_notice"] == metadata["license_notice"]
    assert get_task(db, "fixture", "mate") == task
    assert get_task(db, "other", "mate") is None
    assert collections(db)[0]["excluded"] == 4
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute("UPDATE public_tasks SET prompt_fen=\u0027changed\u0027")
    db.connection.rollback()
    app = create_app(
        db_path=db.path,
        subject="learner",
        actor="operator",
        corpus="fixture",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    assert client.get("/library", base_url="https://coach.invalid").status_code == 403
    response = client.get(
        "/library", base_url="https://coach.invalid", headers={"Tailscale-User-Login": "fixture"}
    )
    assert response.status_code == 200
    page = response.get_data(as_text=True)
    assert "<title>Library — Chess coach</title>" in page
    assert page.count("Licensed direct-prompt collections") == 1
    assert b"3 supported" in response.data and b"4 excluded" in response.data
    assert b"Fixture author" in response.data and b"mate" in response.data
    assert b"unsupported objective" in response.data
    assert b"invalid prompt or solution line" in response.data
    _public_mate_workflow(db, white, black, client, monkeypatch, capsys)


def _public_mate_workflow(db, white, black, client, monkeypatch, capsys):
    from chess_coach.unified_session_events import hint, reveal, show, submit
    from chess_coach.unified_sessions import start

    def begin(attempt, key, **kwargs):
        return start(
            db,
            attempt_id=attempt,
            subject="learner",
            source_type="public",
            version="fixture",
            key=key,
            **kwargs,
        )

    white_task = get_task(db, "fixture", "white-m1")
    assert white_task["prompt_fen"] == white.fen()
    assert white_task["license"] == "CC0-1.0" and len(white_task["source_sha256"]) == 64
    with pytest.raises(ValueError, match="qualified training"):
        begin("closed", "mate", training=True)
    assert (
        db.connection.execute("SELECT count(*) FROM unified_training_enrollments").fetchone()[0]
        == 0
    )

    initial = begin("white-alt", "white-m1")
    stored_source = db.connection.execute(
        "SELECT provenance_json FROM unified_sessions WHERE attempt_id='white-alt'"
    ).fetchone()[0]
    binding = json.loads(stored_source)["public_mate"]
    assert binding == {
        "version": "public_mate_in_one_standalone_v1",
        "verifier": "public-mate-legal-v1",
        "source_kind": "external_public",
        "history": "standalone_fresh",
    }
    assert initial["fen"] == white.fen() and initial["learner_color"] == "white"
    with monkeypatch.context() as patch:
        from chess_coach import public_training_source

        patch.setattr(
            public_training_source, "validate_task", lambda *_: pytest.fail("proof on GET")
        )
        page = client.get(
            "/unified/white-alt",
            base_url="https://coach.invalid",
            headers={"Tailscale-User-Login": "fixture"},
        )
    assert page.status_code == 200 and b"earlier game history is unknown" in page.data
    illegal = submit(db, "white-alt", "learner", event_id="illegal", move="c5a4")
    assert illegal["feedback"] == "illegal" and illegal["status"] == "active"
    assisted = hint(db, "white-alt", "learner", event_id="hint")
    assert assisted["assistance_kind"] == "hinted"
    shown = reveal(db, "white-alt", "learner", event_id="reveal")
    assert shown["assistance_kind"] == "revealed"
    assert reveal(db, "white-alt", "learner", event_id="reveal") == shown
    alternate = submit(db, "white-alt", "learner", event_id="answer", move="c5c8")
    assert alternate["status"] == alternate["feedback"] == "objective_verified"
    assert alternate["hints_used"] == 2
    assert submit(db, "white-alt", "learner", event_id="answer", move="c5c8") == alternate
    with pytest.raises(ValueError, match="unknown"):
        show(db, "white-alt", "other")

    # Historical fixture time makes the actual scheduled item due for this plan.
    from chess_coach import unified_session_apply, unified_sessions

    with monkeypatch.context() as patch:
        patch.setattr(unified_sessions, "now", lambda: "2026-01-01T00:00:00+00:00")
        patch.setattr(unified_session_apply, "now", lambda: "2026-01-01T00:00:00+00:00")
        begin("black-alt", "black-m1", training=True)
        alternate_black = submit(db, "black-alt", "learner", event_id="answer", move="c4c1")
    assert alternate_black["status"] == "objective_verified"
    assert chess.Board(alternate_black["fen"]).is_checkmate()
    learning = alternate_black["learning"]
    assert learning["state"] == "completed" and learning["outcome"] == "success"
    assert learning["rating"] == "good" and learning["evidence_id"]
    evidence = db.connection.execute(
        "SELECT * FROM evidence_mappings WHERE id=?", (learning["evidence_id"],)
    ).fetchone()
    assert json.loads(evidence["context_json"])["source"] == "unified_public_m1"
    from chess_coach.mastery_unified_training import training_context

    context, error = training_context(db, evidence)
    assert context is not None and error is None
    assert submit(db, "black-alt", "learner", event_id="answer", move="c4c1") == alternate_black
    from chess_coach.unified_training_complete import complete

    with pytest.raises(ValueError, match="answer does not match"):
        complete(db, "black-alt", "learner", event_id="different")
    review = db.connection.execute(
        "SELECT reviewed_at FROM training_attempts WHERE item_id=?", (learning["item_id"],)
    ).fetchone()[0]
    assert review == "2026-01-01T00:00:00+00:00"
    plan = client.get(
        "/plan", base_url="https://coach.invalid", headers={"Tailscale-User-Login": "fixture"}
    )
    assert plan.status_code == 200
    assert b"Scheduled review is due." in plan.data
    assert b'name="source_type" value="public"' in plan.data
    assert b'name="version" value="fixture"' in plan.data
    assert f'name="item_id" value="{learning["item_id"]}"'.encode() in plan.data
    csrf_match = re.search(r'name="csrf" value="([^"]+)"', plan.get_data(as_text=True))
    assert csrf_match is not None
    csrf = csrf_match.group(1)
    opened = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture", "Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "source_type": "public",
            "version": "fixture",
            "key": "black-m1",
            "training": "1",
            "item_id": str(learning["item_id"]),
        },
    )
    assert opened.status_code == 303
    reopened = opened.headers["Location"].rsplit("/", 1)[-1]
    assert (
        db.connection.execute(
            "SELECT item_id FROM unified_training_enrollments WHERE attempt_id=?", (reopened,)
        ).fetchone()[0]
        == learning["item_id"]
    )

    practice = client.get(
        opened.headers["Location"],
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture"},
    )
    event_match = re.search(r'name="event" value="([^"]+)"', practice.get_data(as_text=True))
    assert event_match is not None
    event = event_match.group(1)
    finished = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers={"Tailscale-User-Login": "fixture", "Origin": "https://coach.invalid"},
        data={"csrf": csrf, "attempt": reopened, "event": event, "move": "c4c1"},
    )
    assert finished.status_code == 303
    assert show(db, reopened, "learner")["learning"]["item_id"] == learning["item_id"]

    begin("assisted", "white-m1", training=True)
    before_due = db.connection.execute(
        """SELECT i.due FROM training_items i JOIN unified_training_enrollments e ON i.id=e.item_id
        WHERE e.attempt_id='assisted'"""
    ).fetchone()[0]
    hint(db, "assisted", "learner", event_id="hint")
    reveal(db, "assisted", "learner", event_id="reveal")
    assisted = submit(db, "assisted", "learner", event_id="answer", move="c5c8")["learning"]
    assert assisted["assistance"] == "assisted" and assisted["evidence_id"] is None
    assert assisted["rating"] is None and assisted["due"] == before_due
    begin("miss", "white-m1", training=True)
    miss = submit(db, "miss", "learner", event_id="answer", move="c5b5")
    assert miss["feedback"] == "incorrect" and miss["status"] == "line_completed"
    assert miss["learning"]["outcome"] == "failure" and miss["learning"]["rating"] == "again"
    answer_time = db.connection.execute(
        "SELECT created_at FROM unified_session_events WHERE attempt_id='miss' AND event_id='answer'"
    ).fetchone()[0]
    recorded_time = db.connection.execute(
        """SELECT t.reviewed_at FROM training_attempts t
        JOIN unified_training_completions c ON c.training_attempt_id=t.id
        WHERE c.attempt_id='miss'"""
    ).fetchone()[0]
    assert recorded_time == answer_time
    assert db.connection.execute("SELECT count(*) FROM training_attempts").fetchone()[0] == 3

    from types import SimpleNamespace

    from chess_coach.cli_unified_practice import handle_move
    from chess_coach.cli_unified_training import handle_start

    handle_start(
        db,
        SimpleNamespace(
            attempt="cli",
            subject="learner",
            source="public",
            version="fixture",
            key="white-m1",
            goal=None,
            training=True,
            training_item_id=None,
        ),
    )
    assert json.loads(capsys.readouterr().out)["status"] == "active"
    handle_move(db, SimpleNamespace(attempt="cli", subject="learner", event="answer", move="c5c8"))
    cli_result = json.loads(capsys.readouterr().out)
    assert cli_result["learning"]["outcome"] == "success"
    assert cli_result["learning"]["rating"] == "good"
    with pytest.raises(ValueError, match="training item"):
        start(
            db,
            attempt_id="other-owner",
            subject="other",
            source_type="public",
            version="fixture",
            key="black-m1",
            training=True,
            item_id=learning["item_id"],
        )

    from chess_coach import unified_capture_completion

    begin("pending", "white-m1", training=True)
    before_evidence = db.connection.execute("SELECT count(*) FROM evidence_mappings").fetchone()[0]
    before_attempts = db.connection.execute("SELECT count(*) FROM training_attempts").fetchone()[0]
    with monkeypatch.context() as patch:

        def fail_review(*args, **kwargs):
            raise ValueError("injected scheduling failure")

        patch.setattr(unified_capture_completion, "review_item_in_transaction", fail_review)
        pending = submit(db, "pending", "learner", event_id="answer", move="c5f8")
    assert pending["learning"]["state"] == "pending"
    assert (
        db.connection.execute("SELECT count(*) FROM evidence_mappings").fetchone()[0]
        == before_evidence
    )
    assert (
        db.connection.execute("SELECT count(*) FROM training_attempts").fetchone()[0]
        == before_attempts
    )
    assert (
        db.connection.execute(
            "SELECT count(*) FROM unified_training_completions WHERE attempt_id='pending'"
        ).fetchone()[0]
        == 0
    )

    stored = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE attempt_id='white-alt' AND event_id='answer'"
    ).fetchone()[0]
    db.connection.execute("DROP TRIGGER immutable_update_public_collections")
    db.connection.execute("UPDATE public_collections SET state='staging' WHERE version='fixture'")
    db.connection.commit()
    with pytest.raises(ValueError, match="stale"):
        show(db, "white-alt", "learner")
    with pytest.raises(ValueError, match="stale"):
        complete(db, "pending", "learner", event_id="answer")
    assert training_context(db, evidence) == (None, "invalid_training_lineage")
    assert (
        db.connection.execute(
            "SELECT count(*) FROM unified_training_completions WHERE attempt_id='pending'"
        ).fetchone()[0]
        == 0
    )
    assert (
        db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE attempt_id='white-alt' AND event_id='answer'"
        ).fetchone()[0]
        == stored
    )


def test_unlicensed_source_and_duplicate_ids_fail_atomically(tmp_path):
    rows = [("same", MATE, "checkmate", ["c5f8"]), ("same", MATE, "checkmate", ["c5c8"])]
    path, manifest, metadata = file_set(tmp_path, rows=rows, license="unknown")
    db = Database(tmp_path / "coach.sqlite")
    db.initialize()
    with pytest.raises(ValueError, match="license"):
        import_collection(db, path, path, manifest, project_root=tmp_path)
    manifest.write_text(json.dumps(metadata | {"license": "CC0-1.0"}))
    with pytest.raises(ValueError, match="duplicate"):
        import_collection(db, path, path, manifest, project_root=tmp_path)
    assert collections(db) == []
