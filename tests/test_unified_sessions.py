"""Direct prompts, alternative handling, history, and private browser practice."""

import json
import re
import sqlite3

import chess
import pytest

from chess_coach.db import Database
from chess_coach.puzzle_sessions import show_attempt as show_legacy
from chess_coach.puzzle_sessions import start_attempt as start_legacy
from chess_coach.unified_session_events import hint, show, submit
from chess_coach.unified_sessions import start
from chess_coach.web import create_app
from chess_coach.web_board import board_rows

FEN = "6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1"


def fixture_db(path):
    db = Database(path)
    db.initialize()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES(\u0027legacy\u0027,\u0027fixture\u0027,\u0027hash\u0027)"
    )
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES(\u0027old\u0027,1,?,\u0027\u0027,\u0027g8h8 c5f8\u0027,1200,80,\u0027[]\u0027,\u0027execute\u0027)""",
        (FEN,),
    )
    db.connection.execute("""INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        VALUES(\u0027public\u0027,\u0027https://example.invalid\u0027,\u0027v1\u0027,\u0027a\u0027,\u0027b\u0027,\u0027fen_csv\u0027,
        \u0027CC0-1.0\u0027,\u0027Fixture\u0027,\u0027CC0 notice\u0027,4,0,\u0027staging\u0027)""")
    rows = [
        (
            1,
            "multi",
            chess.STARTING_FEN,
            "legal_line",
            json.dumps(["e2e4 e7e5 g1f3", "e2e4 c7c5 g1f3", "d2d4 d7d5 c2c4"]),
        ),
        (1, "mate", "7k/8/6K1/2Q5/8/8/8/8 w - - 1 2", "checkmate", json.dumps(["c5f8", "c5c8"])),
        (
            1,
            "promotion",
            "8/P7/8/8/8/8/8/k6K w - - 0 1",
            "promotion",
            json.dumps(["a7a8q", "a7a8n"]),
        ),
    ]
    black = chess.Board()
    black.push_uci("e2e4")
    rows.append((1, "black", black.fen(), "legal_line", json.dumps(["e7e5"])))
    db.connection.executemany("INSERT INTO public_tasks VALUES(?,?,?,?,?)", rows)
    db.connection.execute("UPDATE public_collections SET state=\u0027ready\u0027 WHERE id=1")
    db.connection.commit()
    return db


def begin(db, attempt, source="public", version="public", key="multi", subject="learner"):
    return start(
        db, attempt_id=attempt, subject=subject, source_type=source, version=version, key=key
    )


def test_public_multiline_resume_hints_and_no_hidden_solution(tmp_path):
    db = fixture_db(tmp_path / "coach.sqlite")
    initial = begin(db, "a1")
    assert initial["fen"] == chess.STARTING_FEN and initial["learner_color"] == "white"
    assert "e2e4" not in json.dumps(initial)
    clue = hint(db, "a1", "learner", event_id="h1")
    assert clue["hint"] == "e2" and hint(db, "a1", "learner", event_id="h1") == clue
    illegal = submit(db, "a1", "learner", event_id="bad", move="e2e5")
    assert illegal["feedback"] == "illegal" and illegal["fen"] == initial["fen"]
    result = submit(db, "a1", "learner", event_id="m1", move="e2e4")
    assert result["status"] == "active" and result["opponent_move"] == "c7c5"
    assert submit(db, "a1", "learner", event_id="m1", move="e2e4") == result
    with pytest.raises(ValueError, match="another request"):
        submit(db, "a1", "learner", event_id="m1", move="d2d4")
    db.close()
    db = Database(tmp_path / "coach.sqlite")
    assert show(db, "a1", "learner") == {
        k: v for k, v in result.items() if k not in ("feedback", "opponent_move")
    }
    done = submit(db, "a1", "learner", event_id="m2", move="g1f3")
    assert done["status"] == "line_completed"
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0
    with pytest.raises(ValueError, match="unknown"):
        show(db, "a1", "other")


def test_unlisted_legal_move_needs_verification_and_preserves_orientation(tmp_path):
    db = fixture_db(tmp_path / "coach.sqlite")
    initial = begin(db, "a2")
    result = submit(db, "a2", "learner", event_id="m1", move="g1f3")
    assert result["status"] == "needs_verification" and result["feedback"] == "needs_verification"
    assert result["fen"] != initial["fen"]
    assert submit(db, "a2", "learner", event_id="m1", move="g1f3") == result
    assert board_rows(result["fen"], result["learner_color"])[0][0]["name"] == "a8"
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0


def test_public_mate_promotion_and_legacy_corpus_setup(tmp_path):
    db = fixture_db(tmp_path / "coach.sqlite")
    old = start_legacy(db, attempt_id="old-attempt", version="legacy", puzzle_id="old")
    corpus = begin(db, "c1", source="corpus", version="legacy", key="old")
    assert corpus["fen"] == old["fen"] and corpus["learner_color"] == "white"
    assert submit(db, "c1", "learner", event_id="m1", move="c5f8")["status"] == "line_completed"
    db.close()
    db = Database(tmp_path / "coach.sqlite")
    assert show_legacy(db, "old-attempt") == old
    begin(db, "mate", key="mate")
    assert (
        submit(db, "mate", "learner", event_id="m1", move="c5c8")["status"] == "objective_verified"
    )
    begin(db, "promotion", key="promotion")
    assert (
        submit(db, "promotion", "learner", event_id="m1", move="a7a8n")["status"]
        == "line_completed"
    )
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        db.connection.execute("UPDATE unified_sessions SET prompt_fen=\u0027other\u0027")
    db.connection.rollback()


def token(response, name):
    match = re.search(
        'name="' + re.escape(name) + '" value="([^"]+)"', response.get_data(as_text=True)
    )
    assert match
    return match.group(1)


def test_private_browser_starts_and_completes_direct_prompt(tmp_path):
    db = fixture_db(tmp_path / "coach.sqlite")
    db.close()
    app = create_app(
        db_path=tmp_path / "coach.sqlite",
        subject="learner",
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert library.status_code == 200 and b"Practice mate" in library.data
    csrf = token(library, "csrf")
    posted = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={"csrf": csrf, "source_type": "public", "version": "public", "key": "mate"},
    )
    assert posted.status_code == 303
    resume_url = posted.headers["Location"]
    restarted = create_app(
        db_path=tmp_path / "coach.sqlite",
        subject="learner",
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = restarted.test_client()
    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert resume_url.encode() in library.data
    csrf = token(library, "csrf")
    page = client.get(resume_url, base_url="https://coach.invalid", headers=headers)
    assert page.status_code == 200 and b"c5f8" not in page.data and b"c5c8" not in page.data
    assert b"learner plays white at the bottom" in page.data
    posted = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "attempt": token(page, "attempt"),
            "event": token(page, "event"),
            "move": "c5f8",
        },
    )
    assert posted.status_code == 303
    page = client.get(posted.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert (
        b"Checkmate verified" in page.data
        and b"stated checkmate objective was verified" in page.data
    )


def test_black_orientation_and_subject_bound_idempotency(tmp_path):
    db = fixture_db(tmp_path / "coach.sqlite")
    initial = begin(db, "black", key="black")
    assert initial["learner_color"] == "black"
    assert board_rows(initial["fen"], initial["learner_color"])[0][0]["name"] == "h1"
    assert begin(db, "black", key="black") == initial
    with pytest.raises(ValueError, match="another source"):
        begin(db, "black", key="mate")
    with pytest.raises(ValueError, match="another source"):
        begin(db, "black", key="black", subject="other")
    assert submit(db, "black", "learner", event_id="m1", move="e7e5")["status"] == "line_completed"


def test_schema_v21_upgrade_is_atomic_and_preserves_legacy(tmp_path, monkeypatch):
    from chess_coach import db_recent

    db = Database(tmp_path / "old.sqlite")
    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_unified_sessions", lambda connection: None)
        db.initialize()
    db.connection.execute("PRAGMA user_version=21")
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES(\u0027old\u0027,\u0027fixture\u0027,\u0027hash\u0027)"
    )
    db.connection.commit()
    original = db_recent.add_unified_sessions

    def fail(connection):
        original(connection)
        raise ValueError("synthetic migration failure")

    with monkeypatch.context() as patch:
        patch.setattr(db_recent, "add_unified_sessions", fail)
        with pytest.raises(ValueError, match="synthetic migration failure"):
            db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 21
    assert not db.connection.execute(
        "SELECT 1 FROM sqlite_master WHERE name=\u0027unified_sessions\u0027"
    ).fetchone()
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 27
    assert db.connection.execute("SELECT version FROM puzzle_corpora").fetchone()[0] == "old"


def test_private_browser_multimove_and_corpus_sources(tmp_path):
    db = fixture_db(tmp_path / "coach.sqlite")
    db.close()
    app = create_app(
        db_path=tmp_path / "coach.sqlite",
        subject="learner",
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    origin = "https://coach.invalid"
    library = client.get("/library", base_url=origin, headers=headers)
    assert b"Practice old" in library.data and b"Practice multi" in library.data
    csrf = token(library, "csrf")

    def begin_page(source, version, key):
        response = client.post(
            "/unified/start",
            base_url=origin,
            headers=headers | {"Origin": origin},
            data={"csrf": csrf, "source_type": source, "version": version, "key": key},
        )
        assert response.status_code == 303
        return client.get(response.headers["Location"], base_url=origin, headers=headers)

    def play(page, move):
        response = client.post(
            "/unified/move",
            base_url=origin,
            headers=headers | {"Origin": origin},
            data={
                "csrf": csrf,
                "attempt": token(page, "attempt"),
                "event": token(page, "event"),
                "move": move,
            },
        )
        assert response.status_code == 303
        return client.get(response.headers["Location"], base_url=origin, headers=headers)

    page = begin_page("public", "public", "multi")
    page = play(page, "e2e4")
    assert b"Move played; continue from this position." in page.data and b"g1f3" not in page.data
    page = play(page, "g1f3")
    assert b"Line complete" in page.data
    page = begin_page("corpus", "legacy", "old")
    assert b"c5f8" not in page.data
    page = play(page, "c5f8")
    assert b"Line complete" in page.data


def test_backup_restore_preserves_session_snapshot_and_legacy_attempt(tmp_path):
    from chess_coach.recovery import backup_database, restore_database

    db = fixture_db(tmp_path / "coach.sqlite")
    legacy = start_legacy(db, attempt_id="legacy-attempt", version="legacy", puzzle_id="old")
    begin(db, "unified")
    active = submit(db, "unified", "learner", event_id="m1", move="e2e4")
    backup_database(db.path, tmp_path / "backup.sqlite", project_root=tmp_path)
    restore_database(
        tmp_path / "backup.sqlite", tmp_path / "restored.sqlite", project_root=tmp_path
    )
    restored = Database(tmp_path / "restored.sqlite")
    restored.initialize()
    assert show_legacy(restored, "legacy-attempt") == legacy
    assert show(restored, "unified", "learner")["fen"] == active["fen"]
    assert (
        submit(restored, "unified", "learner", event_id="m2", move="g1f3")["status"]
        == "line_completed"
    )
