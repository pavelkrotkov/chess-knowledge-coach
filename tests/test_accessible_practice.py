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


def test_promotion_choice_and_black_orientation(tmp_path):
    path = tmp_path / "practice.sqlite"
    fixture_db(path).close()
    client = app_for(path).test_client()
    csrf, url, page = begin(client, "black")
    assert b"learner plays black at the bottom" in page.data
    assert page.data.index(b'data-square="h1"') < page.data.index(b'data-square="a1"')
    result = post(client, "/unified/move", csrf, **fields(page), move="e5", promotion="")
    assert result.status_code == 303
    assert b"Line complete" in client.get(url, base_url=ORIGIN, headers=HEADERS).data
    csrf, url, page = begin(client, "promotion")
    invalid = post(client, "/unified/move", csrf, **fields(page), move="a7a8", promotion="k")
    assert invalid.status_code == 400
    result = post(client, "/unified/move", csrf, **fields(page), move="a7a8", promotion="n")
    assert result.status_code == 303
    assert b"Line complete" in client.get(url, base_url=ORIGIN, headers=HEADERS).data


def test_legacy_hint_reveal_does_not_fabricate_evidence(setup):
    path, app, evidence = setup
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture-login"}
    origin = "https://coach.invalid"
    detail = client.get(f"/evidence/{evidence}", base_url=origin, headers=headers)
    csrf = token(detail, "csrf")
    reviewed = client.post(
        f"/evidence/{evidence}/review",
        base_url=origin,
        headers=headers | {"Origin": origin},
        data={"csrf": csrf, "decision": "accept"},
    )
    assert reviewed.status_code == 303
    start = client.post(
        "/practice/start",
        base_url=origin,
        headers=headers | {"Origin": origin},
        data={"csrf": csrf, "version": "fixture-v1", "puzzle_id": "puzzle"},
    )
    assert start.status_code == 303
    page = client.get("/practice", base_url=origin, headers=headers)
    data = {
        "csrf": csrf,
        "attempt": token(page, "attempt"),
        "event": token(page, "event"),
        "item_id": token(page, "item_id"),
    }
    hinted = client.post(
        "/practice/hint", base_url=origin, headers=headers | {"Origin": origin}, data=data
    )
    assert hinted.status_code == 303
    page = client.get("/practice", base_url=origin, headers=headers)
    assert b"Hint: consider a piece on c5" in page.data and b"Qf8#" not in page.data
    data.update(event=token(page, "event"))
    revealed = client.post(
        "/practice/reveal", base_url=origin, headers=headers | {"Origin": origin}, data=data
    )
    assert revealed.status_code == 200 and b"Qf8" in revealed.data
    page = client.get("/practice", base_url=origin, headers=headers)
    data.update(event=token(page, "event"), move="Qf8#", promotion="")
    moved = client.post(
        "/practice/move", base_url=origin, headers=headers | {"Origin": origin}, data=data
    )
    assert moved.status_code == 303
    again = client.post(
        "/practice/move", base_url=origin, headers=headers | {"Origin": origin}, data=data
    )
    assert again.status_code == 303
    db = Database(path)
    row = db.connection.execute(
        "SELECT evidence_reason,evidence_id FROM training_completions"
    ).fetchone()
    assert tuple(row) == ("hint_used", None)
    assert db.connection.execute("SELECT hints_used FROM puzzle_sessions").fetchone()[0] == 2
    db.close()


def test_stale_own_game_reveal_is_rejected_without_new_hint(tmp_path, monkeypatch):
    from chess_coach.evidence_review import review_evidence
    from chess_coach.material_detector import process_decision
    from chess_coach.unified_own_game import VERSION, list_candidates
    from tests.test_material_pipeline import LEARNER, make_protection_game

    path = tmp_path / "own.sqlite"
    db = make_protection_game(path, monkeypatch)
    evidence = process_decision(db, 1, LEARNER)["evidence_ids"][0]
    key = list_candidates(db, LEARNER)["candidates"][0]["key"]
    db.close()
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="operator",
        corpus="legacy",
        login="fixture",
        origin=ORIGIN,
    )
    client = app.test_client()
    library = client.get("/library", base_url=ORIGIN, headers=HEADERS)
    csrf = token(library, "csrf")
    response = post(
        client, "/unified/start", csrf, source_type="own-game", version=VERSION, key=key
    )
    page = client.get(response.headers["Location"], base_url=ORIGIN, headers=HEADERS)
    db = Database(path)
    review_evidence(db, evidence, decision="reject", actor="fixture_reviewer")
    db.close()
    revealed = post(client, "/unified/reveal", csrf, **fields(page))
    assert revealed.status_code == 400 and b"d4d5" not in revealed.data
    db = Database(path)
    assert db.connection.execute("SELECT COUNT(*) FROM unified_session_events").fetchone()[0] == 0
    db.close()


def test_unhinted_legacy_san_retry_keeps_verified_feedback(setup):
    path, app, evidence = setup
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture-login", "Origin": ORIGIN}
    page = client.get(f"/evidence/{evidence}", base_url=ORIGIN, headers=headers)
    csrf = token(page, "csrf")
    client.post(
        f"/evidence/{evidence}/review",
        base_url=ORIGIN,
        headers=headers,
        data={"csrf": csrf, "decision": "accept"},
    )
    started = client.post(
        "/practice/start",
        base_url=ORIGIN,
        headers=headers,
        data={"csrf": csrf, "version": "fixture-v1", "puzzle_id": "puzzle"},
    )
    assert started.status_code == 303
    page = client.get("/practice", base_url=ORIGIN, headers=headers)
    data = {
        "csrf": csrf,
        "attempt": token(page, "attempt"),
        "event": token(page, "event"),
        "item_id": token(page, "item_id"),
        "move": "Qf8#",
        "promotion": "",
    }
    assert (
        client.post("/practice/move", base_url=ORIGIN, headers=headers, data=data).status_code
        == 303
    )
    assert (
        client.post("/practice/move", base_url=ORIGIN, headers=headers, data=data).status_code
        == 303
    )
    db = Database(path)
    row = db.connection.execute(
        "SELECT evidence_reason,evidence_id FROM training_completions"
    ).fetchone()
    assert row["evidence_reason"] == "verified_mate_in_one" and row["evidence_id"] is not None
    assert db.connection.execute("SELECT COUNT(*) FROM training_completions").fetchone()[0] == 1
    db.close()
