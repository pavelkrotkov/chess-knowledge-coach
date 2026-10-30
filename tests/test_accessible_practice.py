"""Accessible interaction keeps server validation and hidden lines intact."""

from chess_coach.db import Database
from chess_coach.web import create_app
from tests.test_unified_sessions import fixture_db, token
from tests.test_web import setup as setup

ORIGIN = "https://coach.invalid"
HEADERS = {"Tailscale-User-Login": "fixture"}


def app_for(path):
    return create_app(
        db_path=path,
        subject="learner",
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin=ORIGIN,
    )


def post(client, path, csrf, **values):
    return client.post(
        path, base_url=ORIGIN, headers=HEADERS | {"Origin": ORIGIN}, data={"csrf": csrf, **values}
    )


def begin(client, key):
    library = client.get("/library", base_url=ORIGIN, headers=HEADERS)
    csrf = token(library, "csrf")
    response = post(client, "/unified/start", csrf, source_type="public", version="public", key=key)
    assert response.status_code == 303
    return (
        csrf,
        response.headers["Location"],
        client.get(response.headers["Location"], base_url=ORIGIN, headers=HEADERS),
    )


def fields(page):
    return {"attempt": token(page, "attempt"), "event": token(page, "event")}


def test_san_retry_and_read_only_navigation_show_only_played_line(tmp_path):
    path = tmp_path / "practice.sqlite"
    fixture_db(path).close()
    client = app_for(path).test_client()
    csrf, url, page = begin(client, "multi")
    assert b'data-square="e2"' in page.data and b'aria-label="e2 white pawn"' in page.data
    assert (
        b"data-move-board" in page.data
        and b"script-src 'self'" in page.headers["Content-Security-Policy"].encode()
    )
    assert b"g1f3" not in page.data and b"Nf3" not in page.data
    assert b'name="move"' in page.data and b'name="promotion"' in page.data
    event = fields(page)
    assert post(client, "/unified/move", csrf, **event, move="e4", promotion="").status_code == 303
    assert post(client, "/unified/move", csrf, **event, move="e4", promotion="").status_code == 303
    page = client.get(url, base_url=ORIGIN, headers=HEADERS)
    assert b"Move played; continue" in page.data and b"g1f3" not in page.data
    earlier = client.get(url + "?step=1", base_url=ORIGIN, headers=HEADERS)
    assert b"You: e4" in earlier.data and b"Reviewing a previous position" in earlier.data
    assert b'id="move"' not in earlier.data and b"Next position" in earlier.data
    assert b"g1f3" not in earlier.data and b"Nf3" not in earlier.data
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM unified_session_events").fetchone()[0] == 1
    db.close()


def test_invalid_move_hint_and_explicit_reveal(tmp_path):
    path = tmp_path / "practice.sqlite"
    fixture_db(path).close()
    client = app_for(path).test_client()
    csrf, url, page = begin(client, "multi")
    assert b"g1f3" not in page.data and b"Nf3" not in page.data
    result = post(client, "/unified/move", csrf, **fields(page), move="e9", promotion="")
    assert result.status_code == 303
    page = client.get(url, base_url=ORIGIN, headers=HEADERS)
    assert b"That move is not legal" in page.data
    event = fields(page)
    assert post(client, "/unified/reveal", "wrong", **event).status_code == 403
    revealed = post(client, "/unified/reveal", csrf, **event)
    assert revealed.status_code == 200 and b"Nf3" in revealed.data and b"e4" in revealed.data
    assert b"View position after Nf3" in revealed.data and b"Next move" in revealed.data
    replay = post(client, "/unified/reveal", csrf, **event)
    assert replay.status_code == 200 and b"Nf3" in replay.data
    db = Database(path)
    assert db.connection.execute("SELECT hints_used FROM unified_sessions").fetchone()[0] == 1
    assert db.connection.execute("SELECT COUNT(*) FROM evidence_mappings").fetchone()[0] == 0
    db.close()
