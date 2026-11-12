"""Direct prompts, alternative handling, history, and private browser practice."""

import json
import re

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
        (1, "mate-alt", "7k/8/6K1/2Q5/8/8/8/8 w - - 1 2", "checkmate", json.dumps(["c5f8"])),
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
    from chess_coach.objective_contract import VERSION as MATE_ONE_VERSION

    db.connection.execute(
        """INSERT INTO public_collections(version,source_url,source_revision,source_sha256,
        content_sha256,content_format,license,attribution,license_notice,accepted,excluded,state)
        SELECT ?,source_url,source_revision,source_sha256,content_sha256,content_format,
        license,attribution,license_notice,2,0,'staging' FROM public_collections WHERE id=1""",
        (MATE_ONE_VERSION,),
    )
    db.connection.execute(
        """INSERT INTO public_tasks SELECT 2,task_id,prompt_fen,objective,lines_json
        FROM public_tasks WHERE collection_id=1 AND task_id='mate-alt'"""
    )
    db.connection.execute(
        """INSERT INTO public_tasks SELECT 2,task_id,prompt_fen,objective,lines_json
        FROM public_tasks WHERE collection_id=1 AND task_id='multi'"""
    )
    db.connection.execute("UPDATE public_collections SET state='ready' WHERE id=2")
    db.connection.commit()
    return db


def begin(db, attempt, source="public", version="public", key="multi", subject="learner"):
    return start(
        db, attempt_id=attempt, subject=subject, source_type=source, version=version, key=key
    )


def _check_neutral_recognition(monkeypatch):
    import sqlite3
    from urllib.parse import urlparse

    import chess.pgn

    from chess_coach import recognition_current, recognition_scan, web_recognition
    from chess_coach.recognition_proof import prove
    from chess_coach.recognition_view import view
    from chess_coach.related_capture_assessment import setup

    db = Database(":memory:")
    db.initialize()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum,state) VALUES('checks','fixture','hash','staging')"
    )
    corpus = db.connection.execute("SELECT id FROM puzzle_corpora").fetchone()[0]
    for file in "abcdef":
        board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 b - - 0 1")
        board.set_piece_at(chess.parse_square(file + "7"), chess.Piece(chess.PAWN, chess.BLACK))
        game_id = "owned" if file == "a" else "future" if file == "e" else "external" + file
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES(?,?,?, ?,?,1200,80,'[]','unknown')""",
            (
                file,
                corpus,
                board.fen(),
                "https://lichess.org/" + game_id,
                file + "7" + file + "6 d1d4",
            ),
        )
        db.connection.execute(
            "INSERT INTO puzzle_themes VALUES(?,?,'hangingPiece',1200)", (corpus, file)
        )
    mate = chess.Board("6k1/1p3ppp/8/8/8/8/8/R4K2 b - - 0 1")
    for key, board, solution in (
        ("mate-a", mate, "b7b6 a1a8"),
        ("mate-b", mate.mirror(), "b2b3 a8a1"),
    ):
        db.connection.execute(
            """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
            VALUES(?,?,?,'https://example.invalid',?,1200,80,'[]','unknown')""",
            (key, corpus, board.fen(), solution),
        )
        db.connection.execute("INSERT INTO puzzle_themes VALUES(?,?,'mateIn1',1200)", (corpus, key))
    mixed = mate.copy()
    mixed.set_piece_at(chess.B1, chess.Piece(chess.BISHOP, chess.BLACK))
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('mixed',?,?,'https://example.invalid','b7b6 a1a8',1200,80,'[]','unknown')""",
        (corpus, mixed.fen()),
    )
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,rating_deviation,themes_json,objective)
        VALUES('mixed-unknown',?,?,'https://example.invalid','b7b6 a1a8',1200,80,'[]','unknown')""",
        (corpus, "6k1/1p3ppp/8/8/8/8/1r6/Rn3K2 b - - 0 1"),
    )
    db.connection.execute("UPDATE puzzle_corpora SET state='ready' WHERE id=?", (corpus,))
    pgn = '[White "Learner"]\n[Black "Opponent"]\n[Result "*"]\n\n1. e4 *'
    db.connection.execute(
        "INSERT INTO games(source,source_id,pgn,white,black,result) VALUES('lichess','owned',?,'Learner','Opponent','*')",
        (pgn,),
    )
    db.connection.commit()
    assert prove(db, "checks", "mixed", "mate", setup(db, "checks", "mixed")) is None
    from chess_coach.mate_proof import immediate_mates
    from chess_coach.objective_capture_judge import judge

    unknown = setup(db, "checks", "mixed-unknown")
    assert len(immediate_mates(unknown[0])) == 1
    competing = next(move for move in unknown[0].legal_moves if unknown[0].is_capture(move))
    assert (
        judge(
            unknown[0],
            competing,
            "bounded_material_gain",
            competing.to_square,
            3,
            lambda: 0.0,
            0.0,
            1.5,
            {},
        )["status"]
        == "unresolved"
    )
    assert prove(db, "checks", "mixed-unknown", "mate", unknown) is None

    monkeypatch.setattr(web_recognition, "database", lambda: db)
    app = create_app(
        db_path=":memory:",
        subject="learner",
        actor="fixture",
        corpus="checks",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    base, headers = "https://coach.invalid", {"Tailscale-User-Login": "fixture"}
    assert client.get("/recognition", base_url=base).status_code == 403
    landing = client.get("/recognition", base_url=base, headers=headers)
    csrf = token(landing, "csrf")
    assert (
        client.post(
            "/recognition/start", base_url=base, headers=headers, data={"csrf": csrf}
        ).status_code
        == 403
    )
    post_headers = headers | {"Origin": base}

    def begin(prefer):
        monkeypatch.setattr(recognition_scan.secrets, "randbelow", lambda _: prefer)
        response = client.post(
            "/recognition/start", base_url=base, headers=post_headers, data={"csrf": csrf}
        )
        assert response.status_code == 303
        attempt = urlparse(response.headers["Location"]).path.rsplit("/", 1)[-1]
        page = client.get(response.headers["Location"], base_url=base, headers=headers)
        assert page.status_code == 200 and b"Which opportunity is available" in page.data
        assert b"direct capture that wins at least three material points" in page.data
        assert b"Checkmate in one move" in page.data and b"I am unsure" in page.data
        assert b"Rxd4" not in page.data and b"Ra8" not in page.data
        assert b"https://lichess.org" not in page.data and b"mate-a" not in page.data
        return attempt

    def respond(attempt, action, choice=None):
        return client.post(
            f"/recognition/{attempt}/answer",
            base_url=base,
            headers=post_headers,
            data={"csrf": csrf, "action": action, **({"choice": choice} if choice else {})},
        )

    capture = begin(0)
    record = db.connection.execute(
        "SELECT source_key,cue_status FROM recognition_attempts WHERE attempt_id=?", (capture,)
    ).fetchone()
    assert tuple(record) == ("b", "uncued")  # The owned source game is excluded.
    from chess_coach.related_capture_probe import position_probe

    key = db.connection.execute(
        "SELECT prompt_key FROM recognition_attempts WHERE attempt_id=?", (capture,)
    ).fetchone()[0]
    assert position_probe(db, "learner", "learner")(key)
    assert respond(capture, "answer", "mate").status_code == 303
    assert view(db, "learner", capture)["outcome"] == "incorrect"
    assert respond(capture, "answer", "mate").status_code == 303
    assert respond(capture, "answer", "capture").status_code == 400
    start(
        db,
        attempt_id="later-replay",
        subject="learner",
        source_type="corpus",
        version="checks",
        key="b",
    )
    assert view(db, "learner", capture)["outcome"] == "incorrect"

    mate_attempt = begin(1)
    assert respond(mate_attempt, "answer", "mate").status_code == 303
    assert view(db, "learner", mate_attempt)["outcome"] == "correct"
    assisted = begin(0)
    assert respond(assisted, "reveal").status_code == 303
    assert view(db, "learner", assisted)["assisted"]
    uncertain = begin(1)
    black_page = client.get(f"/recognition/{uncertain}", base_url=base, headers=headers)
    assert b"Black to move" in black_page.data
    assert respond(uncertain, "answer", "uncertain").status_code == 303
    assert view(db, "learner", uncertain)["outcome"] == "ungraded"

    exposed = begin(0)
    exposed_row = db.connection.execute(
        "SELECT source_key FROM recognition_attempts WHERE attempt_id=?", (exposed,)
    ).fetchone()
    start(
        db,
        attempt_id="prior-replay",
        subject="learner",
        source_type="corpus",
        version="checks",
        key=exposed_row["source_key"],
    )
    assert view(db, "learner", exposed)["status"] == "unavailable"
    assert respond(exposed, "answer", "capture").status_code == 400

    newly_owned = begin(0)
    db.connection.execute(
        "INSERT INTO games(source,source_id,pgn,white,black,result) VALUES('lichess','future',?,'Learner','Opponent','*')",
        (pgn,),
    )
    db.connection.commit()
    assert view(db, "learner", newly_owned)["status"] == "unavailable"
    assert respond(newly_owned, "answer", "capture").status_code == 400
    with monkeypatch.context() as patch:
        patch.setattr(recognition_current, "VERSION", "revoked")
        assert view(db, "learner", mate_attempt)["status"] == "unavailable"

    class ChangedVersion:
        def __init__(self, connection):
            self.connection = connection
            self.count = 0

        def execute(self, sql, *args):
            if sql == "PRAGMA data_version":
                self.count += 1
                return type("VersionRow", (), {"fetchone": lambda _: (self.count,)})()
            return self.connection.execute(sql, *args)

        def __getattr__(self, name):
            return getattr(self.connection, name)

    with monkeypatch.context() as patch:
        patch.setattr(db, "connection", ChangedVersion(db.connection))
        assert view(db, "learner", mate_attempt)["status"] == "unavailable"

    raced = begin(0)
    with monkeypatch.context() as patch:
        patch.setattr(db, "connection", ChangedVersion(db.connection))
        assert respond(raced, "answer", "capture").status_code == 400
    assert view(db, "learner", raced)["status"] == "active"
    from chess_coach import recognition_view

    def timeout(*_args):
        raise ValueError("recognition familiarity deadline reached")

    with monkeypatch.context() as patch:
        patch.setattr(recognition_view, "novel", timeout)
        timed = client.get(f"/recognition/{raced}", base_url=base, headers=headers)
    assert b"timed out" in timed.data

    # A different newly imported game can start at the prompt without indexing that initial board.
    from chess_coach import recognition_game_frontier
    from chess_coach.ingest import ingest_pgn

    saved = db.connection.execute(
        "SELECT prompt_fen,prompt_key,game_watermark FROM recognition_attempts WHERE attempt_id=?",
        (raced,),
    ).fetchone()
    initial_board = chess.Board(saved["prompt_fen"])
    custom = chess.pgn.Game()
    custom.setup(initial_board)
    custom.headers.update({"White": "Learner", "Black": "Opponent", "Result": "*"})
    custom.add_variation(next(iter(initial_board.legal_moves)))
    ingest_pgn(db, str(custom))
    assert (
        db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0] > saved["game_watermark"]
    )
    assert not position_probe(db, "learner", "learner", exclude_recognition=raced)(
        saved["prompt_key"]
    )
    with monkeypatch.context() as patch:
        patch.setattr(recognition_game_frontier, "MAX_NEW_GAMES", 0)
        bounded = client.get(f"/recognition/{raced}", base_url=base, headers=headers)
    assert b"Too many newly imported games" in bounded.data
    assert view(db, "learner", raced)["status"] == "unavailable"
    stale = client.get(f"/recognition/{raced}", base_url=base, headers=headers)
    assert b"first-encounter status is unavailable" in stale.data
    assert b"Which opportunity is available" not in stale.data
    assert respond(raced, "answer", "capture").status_code == 400
    assert view(db, "learner", capture)["outcome"] == "incorrect"

    history = client.get("/recognition", base_url=base, headers=headers)
    assert b"View result" in history.data and b"Resume a check" in history.data
    count = db.connection.execute("SELECT COUNT(*) FROM recognition_events").fetchone()[0]
    assert count == 4
    for table in (
        "mastery_events",
        "mastery_states",
        "training_items",
        "training_attempts",
        "training_completions",
        "objective_requests",
    ):
        assert db.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    with pytest.raises(sqlite3.IntegrityError):
        db.connection.execute(
            "UPDATE recognition_events SET answer='mate' WHERE attempt_id=?", (capture,)
        )
    db.connection.rollback()
    db.connection.execute("PRAGMA user_version=31")
    db.initialize()
    assert db.connection.execute("PRAGMA user_version").fetchone()[0] == 32
    assert db.connection.execute("SELECT COUNT(*) FROM recognition_events").fetchone()[0] == count
    db.close()


def test_public_multiline_resume_hints_and_no_hidden_solution(tmp_path, monkeypatch):
    _check_neutral_recognition(monkeypatch)
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

    # A legal alternate actual mate needs no worker; other public deviations
    # remain explicitly ungraded without changing the immutable event schema.
    begin(db, "alternate-mate", key="mate-alt")
    alternate = submit(db, "alternate-mate", "learner", event_id="m", move="c5c8")
    assert alternate["status"] == alternate["feedback"] == "objective_verified"
    begin(db, "ungraded")
    other = submit(db, "ungraded", "learner", event_id="m", move="g1f3")
    assert other["status"] == "ungraded" and other["feedback"] == "ungraded"
    assert show(db, "ungraded", "learner")["public_outcome"] == "ungraded"
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0
    assert db.connection.execute("SELECT COUNT(*) FROM training_attempts").fetchone()[0] == 0

    from chess_coach.objective_contract import VERSION as MATE_ONE_VERSION
    from chess_coach.unified_session_branch import move_state
    from chess_coach.unified_session_legal_move import apply
    from chess_coach.unified_session_state import recent
    from chess_coach.unified_session_state import view as current_view

    begin(db, "collision", version=MATE_ONE_VERSION, key="mate-alt")
    assert (
        submit(db, "collision", "learner", event_id="m", move="c5c8")["status"]
        == "objective_verified"
    )
    related = {
        "source_type": "public",
        "objective": "checkmate",
        "next_index": 0,
        "source_version": MATE_ONE_VERSION,
        "provenance_json": json.dumps({"related_mate": {}}),
    }
    related_result = apply(
        related,
        chess.Board("7k/8/6K1/2Q5/8/8/8/8 w - - 1 2"),
        [["c5f8"]],
        [0],
        chess.Move.from_uci("c5c8"),
    )
    assert related_result["status"] == "needs_verification"
    assert related_result["feedback"] == "ungraded"
    from chess_coach.unified_public_outcome import outcome as public_outcome

    related.update(
        status="needs_verification",
        current_fen=related_result["fen"],
        attempt_id="related",
        source_key="private-related",
        learner_color="white",
        hints_used=0,
        started_at="now",
        finished_at="now",
    )
    assert public_outcome(related) == "ungraded"
    related_view = current_view(related)
    assert related_view["status"] == "ungraded" and "source_key" not in related_view
    from flask import render_template

    related_app = create_app(
        db_path=tmp_path / "coach.sqlite",
        subject="learner",
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin="https://coach.invalid",
    )
    with related_app.test_request_context("/"):
        related_page = render_template(
            "unified_practice.html",
            state=related_view,
            board=board_rows(related_view["fen"], "white"),
            steps=[{"fen": related_view["fen"], "label": "Current"}],
            step=0,
            at_current=True,
            board_label="Position",
            event="e",
            csrf="token",
            notice=None,
        )
    assert "no verification was queued" in related_page
    assert "Return to the library or coaching" in related_page
    assert "Restart this exercise" not in related_page

    begin(db, "collision-other", version=MATE_ONE_VERSION, key="multi")
    collision = submit(db, "collision-other", "learner", event_id="m", move="g1f3")
    assert collision["status"] == "ungraded" and "verification" not in show(
        db, "collision-other", "learner"
    )
    assert db.connection.execute("SELECT COUNT(*) FROM objective_requests").fetchone()[0] == 0

    # Simulate a pre-fix immutable event and leave its stored response untouched.
    begin(db, "legacy-unlisted", key="mate-alt")
    begin(db, "legacy-other")

    def legacy_view(row):
        result = current_view(row)
        result["status"] = row["status"]
        result.pop("public_outcome", None)
        result.pop("source_key", None)
        return result

    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.unified_session_apply.view", legacy_view)
        patch.setattr(
            "chess_coach.unified_session_legal_move._unmatched",
            lambda row, board, index, candidates: move_state(
                board, "needs_verification", "needs_verification", index, candidates
            ),
        )
        legacy = submit(db, "legacy-unlisted", "learner", event_id="m", move="c5c8")
        legacy_other = submit(db, "legacy-other", "learner", event_id="m", move="g1f3")
    assert legacy_other["status"] == "needs_verification"
    assert show(db, "legacy-other", "learner")["status"] == "ungraded"
    assert submit(db, "legacy-other", "learner", event_id="m", move="g1f3") == legacy_other
    stored = db.connection.execute(
        "SELECT response_json FROM unified_session_events WHERE attempt_id=? AND event_id=?",
        ("legacy-unlisted", "m"),
    ).fetchone()[0]
    assert legacy["status"] == "needs_verification"
    assert show(db, "legacy-unlisted", "learner")["public_outcome"] == "checkmate_reached"
    assert submit(db, "legacy-unlisted", "learner", event_id="m", move="c5c8") == legacy
    assert (
        db.connection.execute(
            "SELECT response_json FROM unified_session_events WHERE attempt_id=? AND event_id=?",
            ("legacy-unlisted", "m"),
        ).fetchone()[0]
        == stored
    )
    assert (
        next(item for item in recent(db, "learner") if item["attempt_id"] == "ungraded")["status"]
        == "ungraded"
    )


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
        data={"csrf": csrf, "source_type": "public", "version": "public", "key": "mate-alt"},
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
            "move": "c5c8",
        },
    )
    assert posted.status_code == 303
    page = client.get(posted.headers["Location"], base_url="https://coach.invalid", headers=headers)
    assert (
        b"Checkmate verified" in page.data
        and b"stated checkmate objective was verified" in page.data
    )

    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    csrf = token(library, "csrf")
    started = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={"csrf": csrf, "source_type": "public", "version": "public", "key": "multi"},
    )
    page = client.get(
        started.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    submitted = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "attempt": token(page, "attempt"),
            "event": token(page, "event"),
            "move": "g1f3",
        },
    )
    page = client.get(
        submitted.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Status: Ungraded" in page.data and b"no verification was queued" in page.data
    assert b"Restart this exercise" in page.data
    restarted = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={
            "csrf": csrf,
            "source_type": "public",
            "version": token(page, "version"),
            "key": token(page, "key"),
        },
    )
    assert (
        restarted.status_code == 303
        and restarted.headers["Location"] != submitted.headers["Location"]
    )
    page = client.get(
        restarted.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"Status: In progress" in page.data
    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert b"Ungraded" in library.data


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
