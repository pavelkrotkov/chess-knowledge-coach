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
    assert cookie.startswith("__Host-chess_coach_session=")
    assert "Secure" in cookie and "HttpOnly" in cookie and "SameSite=Strict" in cookie
    assert "Path=/" in cookie and "Domain=" not in cookie
    assert page.headers["Cache-Control"] == "no-store"
    assert page.headers["Referrer-Policy"] == "same-origin"
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
    assert (
        client.post(
            endpoint,
            base_url=ORIGIN,
            headers={**HEADERS, "Origin": "null"},
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
        post(
            client,
            "/practice/move",
            csrf,
            attempt=token(page, "attempt"),
            item_id=token(page, "item_id"),
            event=token(page, "event"),
            move="c5c8",
        ).status_code
        == 303
    )
    page = client.get("/practice", base_url=ORIGIN, headers=HEADERS)
    assert (
        b"Solved" in page.data
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


def test_real_unix_server_enforces_identity_origin_and_csrf(setup):
    import http.client
    import os
    import shutil
    import socket
    import subprocess
    import sys
    import tempfile
    import time
    from urllib.parse import urlencode

    source_db, _, evidence_id = setup
    with tempfile.TemporaryDirectory(prefix="wh-") as directory:
        root = Path(directory)
        path = root / "web.sock"
        db_path = root / "coach.sqlite"
        shutil.copyfile(source_db, db_path)
        env = os.environ | {
            "CHESS_PROJECT_ROOT": str(root),
            "CHESS_DB": str(db_path),
            "CHESS_WEB_SOCKET": str(path),
            "CHESS_SUBJECT": "learner",
            "CHESS_REVIEW_ACTOR": "fixture-reviewer",
            "CHESS_CORPUS": "fixture-v1",
            "CHESS_TAILSCALE_LOGIN": LOGIN,
            "CHESS_WEB_ORIGIN": ORIGIN,
        }

        class UnixConnection(http.client.HTTPConnection):
            def connect(self):
                self.sock = socket.socket(socket.AF_UNIX)
                self.sock.settimeout(5)
                self.sock.connect(str(path))

        def request(method, route, *, headers=None, data=None):
            client = UnixConnection("localhost", timeout=5)
            body = urlencode(data or {}) if method == "POST" else None
            supplied = {"Host": "localhost", "X-Forwarded-Host": "coach.invalid"}
            supplied.update(headers or {})
            if body is not None:
                supplied["Content-Type"] = "application/x-www-form-urlencoded"
            client.request(method, route, body=body, headers=supplied)
            response = client.getresponse()
            status, response_headers, payload = response.status, response.headers, response.read()
            client.close()
            return status, response_headers, payload

        proc = subprocess.Popen(
            [sys.executable, "-m", "chess_coach.web_server"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            deadline = time.monotonic() + 10
            while not path.exists() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            assert path.is_socket() and proc.poll() is None
            route = f"/evidence/{evidence_id}"
            assert request("GET", route)[0] == 403
            assert request("GET", route, headers={"Tailscale-User-Login": "wrong"})[0] == 403
            assert (
                request(
                    "GET",
                    route,
                    headers={**HEADERS, "Host": "coach.invalid", "X-Forwarded-Host": "localhost"},
                )[0]
                == 403
            )
            status, headers, body = request(
                "GET",
                route,
                headers={
                    **HEADERS,
                    "Origin": "https://evil.invalid",
                    "X-Forwarded-Host": "evil.invalid",
                },
            )
            assert status == 200 and headers.get("Access-Control-Allow-Origin") is None
            assert headers["Referrer-Policy"] == "same-origin"
            cookie = headers["Set-Cookie"]
            assert cookie.startswith("__Host-chess_coach_session=")
            assert (
                "Secure" in cookie
                and "HttpOnly" in cookie
                and "SameSite=Strict" in cookie
                and "Path=/" in cookie
                and "Domain=" not in cookie
            )
            quote = bytes([34])
            marker = b"name=" + quote + b"csrf" + quote + b" value=" + quote
            csrf = body.split(marker, 1)[1].split(quote, 1)[0].decode()
            post_route = route + "/review"
            authenticated = {**HEADERS, "Cookie": cookie.split(";", 1)[0]}
            form = {"csrf": csrf, "decision": "accept"}
            no_identity = {"Cookie": authenticated["Cookie"], "Origin": ORIGIN}
            assert request("POST", post_route, headers=no_identity, data=form)[0] == 403
            assert (
                request(
                    "POST",
                    post_route,
                    headers={**no_identity, "Tailscale-User-Login": "wrong"},
                    data=form,
                )[0]
                == 403
            )
            assert request("POST", post_route, headers=authenticated, data=form)[0] == 403
            assert (
                request("POST", post_route, headers={**authenticated, "Origin": "null"}, data=form)[
                    0
                ]
                == 403
            )
            assert (
                request(
                    "POST",
                    post_route,
                    headers={**authenticated, "Origin": "https://evil.invalid"},
                    data=form,
                )[0]
                == 403
            )
            assert (
                request(
                    "POST",
                    post_route,
                    headers={**authenticated, "Origin": ORIGIN},
                    data={"decision": "accept"},
                )[0]
                == 403
            )
            assert (
                request(
                    "POST",
                    post_route,
                    headers={**authenticated, "Origin": ORIGIN},
                    data={"csrf": "wrong", "decision": "accept"},
                )[0]
                == 403
            )
            check = Database(db_path)
            assert (
                check.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[
                    0
                ]
                == 0
            )
            check.close()
            assert (
                request(
                    "POST",
                    post_route,
                    headers={**authenticated, "Origin": ORIGIN, "X-Forwarded-Host": "evil.invalid"},
                    data=form,
                )[0]
                == 303
            )
            check = Database(db_path)
            assert (
                check.connection.execute("SELECT COUNT(*) FROM evidence_review_events").fetchone()[
                    0
                ]
                == 1
            )
            check.close()
        finally:
            proc.kill()
            proc.wait(timeout=5)
