"""Private browser security and real review-to-practice flow."""

import re
from pathlib import Path
from typing import cast

import chess
import chess.pgn
import pytest

from chess_coach.db import Database
from chess_coach.evidence_review import review_evidence
from chess_coach.ingest import ingest_pgn
from chess_coach.tactical_opportunities import record_game_opportunities
from chess_coach.web import create_app
from chess_coach.web_board import board_rows
from chess_coach.web_paths import inside, socket_directory

ORIGIN = "https://coach.invalid"
LOGIN = "fixture-login"
HEADERS = {"Tailscale-User-Login": LOGIN}
FEN = "6k1/8/6K1/2Q5/8/8/8/8 b - - 0 1"


@pytest.fixture
def setup(tmp_path):
    path = tmp_path / "coach.sqlite"
    db = Database(path)
    db.initialize()
    db.connection.execute(
        "INSERT INTO puzzle_corpora(version,source,checksum) VALUES('fixture-v1','fixture','hash')"
    )
    db.connection.execute(
        """INSERT INTO puzzles(puzzle_id,corpus_id,fen,source,solution,rating,
        rating_deviation,themes_json,objective)
        VALUES ('puzzle',1,?,'','g8h8 c5f8',500,80,'[]','execute')""",
        (FEN,),
    )
    db.connection.commit()
    game = chess.pgn.Game()
    board = chess.Board("8/8/8/8/4Q3/2K5/8/2k5 w - - 0 1")
    game.setup(board)
    game.headers["White"] = "Learner"
    game.headers["Black"] = "Opponent"
    game.add_variation(board.parse_uci("e4d3"))
    ingest_pgn(db, str(game))
    game_id = db.connection.execute("SELECT MAX(id) FROM games").fetchone()[0]
    results = record_game_opportunities(db, game_id, learner="learner")
    evidence_id = cast(list[int], results[0]["evidence_ids"])[0]
    db.close()
    app = create_app(
        db_path=path,
        subject="learner",
        actor="fixture-reviewer",
        corpus="fixture-v1",
        login=LOGIN,
        origin=ORIGIN,
    )
    app.testing = True
    return path, app, evidence_id


def token(response, name="csrf"):
    match = re.search(rb'name="' + name.encode() + rb'" value="([^"]+)"', response.data)
    assert match
    return match.group(1).decode()


def post(client, path, csrf, **values):
    return client.post(
        path, base_url=ORIGIN, headers={**HEADERS, "Origin": ORIGIN}, data={"csrf": csrf, **values}
    )


def test_private_access_and_csrf(setup):
    path, app, evidence_id = setup
    client = app.test_client()
    assert client.get("/", base_url=ORIGIN).status_code == 403
    assert (
        client.get("/", base_url=ORIGIN, headers={"Tailscale-User-Login": "other"}).status_code
        == 403
    )
    assert client.get("/", base_url="https://other.invalid", headers=HEADERS).status_code == 403
    page = client.get(f"/evidence/{evidence_id}", base_url=ORIGIN, headers=HEADERS)
    assert page.status_code == 200
    cookie = page.headers["Set-Cookie"]
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert page.headers["Cache-Control"] == "no-store"
    csrf = token(page)
    endpoint = f"/evidence/{evidence_id}/review"
    assert (
        client.post(
            endpoint, base_url=ORIGIN, headers=HEADERS, data={"csrf": csrf, "decision": "accept"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            endpoint,
            base_url=ORIGIN,
            headers={**HEADERS, "Origin": "https://other.invalid"},
            data={"csrf": csrf, "decision": "accept"},
        ).status_code
        == 403
    )
    assert post(client, endpoint, "wrong", decision="accept").status_code == 403
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[0] == 0
    db.close()


def test_review_practice_completion_and_followup_plan(setup):
    path, app, evidence_id = setup
    client = app.test_client()
    detail = client.get(f"/evidence/{evidence_id}", base_url=ORIGIN, headers=HEADERS)
    assert b"Source game: 1; ply: 1" in detail.data
    assert b"Chess position" in detail.data and b"mate_in_one" in detail.data
    csrf = token(detail)
    assert (
        post(client, f"/evidence/{evidence_id}/review", csrf, decision="accept").status_code == 303
    )
    page = client.get("/plan", base_url=ORIGIN, headers=HEADERS)
    assert b"Find mate in one." in page.data
    assert (
        post(client, "/practice/start", csrf, version="fixture-v1", puzzle_id="puzzle").status_code
        == 303
    )
    page = client.get("/practice", base_url=ORIGIN, headers=HEADERS)
    assert page.status_code == 200 and b"Find mate in one." in page.data
    assert b"c5f8" not in page.data and b"c5c8" not in page.data
    assert (
        post(client, "/practice/move", csrf, event=token(page, "event"), move="c5c8").status_code
        == 303
    )
    page = client.get("/practice", base_url=ORIGIN, headers=HEADERS)
    assert (
        b"solved" in page.data
        and b"Next due:" in page.data
        and b"verified_mate_in_one" in page.data
    )
    next_plan = client.get("/plan", base_url=ORIGIN, headers=HEADERS)
    assert b"No practice items" in next_plan.data
    db = Database(path)
    assert (
        db.connection.execute("SELECT decision FROM evidence_review_events").fetchone()[0]
        == "accept"
    )
    assert db.connection.execute("SELECT COUNT(*) FROM training_completions").fetchone()[0] == 1
    assert (
        db.connection.execute(
            "SELECT COUNT(*) FROM evidence_mappings WHERE human_validated=0"
        ).fetchone()[0]
        == 1
    )
    db.close()


def test_untrusted_review_text_is_escaped(setup):
    path, app, evidence_id = setup
    db = Database(path)
    review_evidence(
        db, evidence_id, decision="accept", actor="fixture", rationale="<script>alert(1)</script>"
    )
    db.close()
    page = app.test_client().get(f"/evidence/{evidence_id}", base_url=ORIGIN, headers=HEADERS)
    assert b"<script>alert(1)</script>" not in page.data
    assert b"&lt;script&gt;alert(1)&lt;/script&gt;" in page.data


def test_board_orientation_and_private_paths(tmp_path):
    board = board_rows(FEN)
    assert board[0][0]["name"] == "h1"
    assert board[-1][-1]["name"] == "a8"
    assert board_rows("invalid") == []
    private = tmp_path / "private"
    private.mkdir(mode=0o700)
    socket = inside(tmp_path, str(private / "web.sock"), existing=False)
    socket_directory(socket)
    private.chmod(0o755)
    with pytest.raises(ValueError, match="private"):
        socket_directory(socket)
    with pytest.raises(ValueError, match="within"):
        inside(tmp_path, str(Path("/") / "outside.sock"), existing=False)
    existing = private / "existing"
    existing.write_text("keep")
    with pytest.raises(ValueError, match="already exists"):
        inside(tmp_path, str(existing), existing=False)
    assert existing.read_text() == "keep"


@pytest.mark.parametrize(
    "origin",
    [
        "http://coach.invalid",
        "https://coach.invalid/path",
        "https://user:pass@coach.invalid",
        "https://coach.invalid?x=1",
    ],
)
def test_invalid_origin_rejected(setup, origin):
    path, _, _ = setup
    with pytest.raises(ValueError):
        create_app(
            db_path=path,
            subject="learner",
            actor="fixture",
            corpus="fixture-v1",
            login=LOGIN,
            origin=origin,
        )


def test_start_revalidates_a_stale_recommendation(setup):
    path, app, _ = setup
    client = app.test_client()
    page = client.get("/plan", base_url=ORIGIN, headers=HEADERS)
    csrf = token(page)
    assert (
        post(client, "/practice/start", csrf, version="fixture-v1", puzzle_id="puzzle").status_code
        == 303
    )
    page = client.get("/practice", base_url=ORIGIN, headers=HEADERS)
    assert (
        post(client, "/practice/move", csrf, event=token(page, "event"), move="c5c8").status_code
        == 303
    )
    assert (
        post(client, "/practice/start", csrf, version="fixture-v1", puzzle_id="puzzle").status_code
        == 400
    )
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM puzzle_sessions").fetchone()[0] == 1
    db.close()


def test_waitress_serves_only_private_unix_socket(setup):
    import socket
    import tempfile
    import threading

    from waitress import create_server

    _, app, _ = setup
    with tempfile.TemporaryDirectory(prefix="browser-") as directory:
        socket_path = Path(directory) / "web.sock"
        server = create_server(app, unix_socket=str(socket_path), unix_socket_perms="600")
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            assert socket_path.stat().st_mode & 0o777 == 0o600
            with socket.socket(socket.AF_UNIX) as client:
                client.settimeout(5)
                client.connect(str(socket_path))
                client.sendall(
                    b"GET / HTTP/1.1\r\nHost: coach.invalid\r\n"
                    b"Tailscale-User-Login: fixture-login\r\nConnection: close\r\n\r\n"
                )
                response = b""
                while data := client.recv(4096):
                    response += data
            assert b"HTTP/1.1 200 OK" in response
            assert b"Processing status" in response
        finally:
            server.close()
            thread.join(timeout=3)


def test_illegal_move_preserves_active_attempt(setup):
    path, app, _ = setup
    client = app.test_client()
    page = client.get("/plan", base_url=ORIGIN, headers=HEADERS)
    csrf = token(page)
    assert (
        post(client, "/practice/start", csrf, version="fixture-v1", puzzle_id="puzzle").status_code
        == 303
    )
    page = client.get("/practice", base_url=ORIGIN, headers=HEADERS)
    response = post(client, "/practice/move", csrf, event=token(page, "event"), move="a1a8")
    assert response.status_code == 303
    page = client.get("/practice", base_url=ORIGIN, headers=HEADERS)
    assert b"not legal" in page.data
    db = Database(path)
    assert db.connection.execute("SELECT status FROM puzzle_sessions").fetchone()[0] == "active"
    assert db.connection.execute("SELECT COUNT(*) FROM training_completions").fetchone()[0] == 0
    db.close()
