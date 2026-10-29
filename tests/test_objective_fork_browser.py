"""The browser exposes and checks an owned fork without revealing its move."""

from chess_coach.objective_worker import process
from chess_coach.web import create_app
from tests.objective_fork_support import SUBJECT, VERSION, owned_fork
from tests.test_unified_sessions import token


def test_browser_owned_fork_start_and_verified_alternative(tmp_path, monkeypatch):
    path = tmp_path / "browser.sqlite"
    db, _ = owned_fork(path, monkeypatch, "f6g5")
    db.close()
    monkeypatch.setattr(
        "chess_coach.web_security.secrets.token_urlsafe",
        lambda size: "A" * (43 if size == 32 else 32),
    )
    app = create_app(
        db_path=path,
        subject=SUBJECT,
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    library = client.get("/library", base_url="https://coach.invalid", headers=headers)
    assert library.status_code == 200 and b"Practice this fork" in library.data
    csrf = token(library, "csrf")
    from chess_coach.db import Database

    db = Database(path)
    evidence = db.connection.execute(
        "SELECT id FROM evidence_mappings WHERE skill='fork'"
    ).fetchone()[0]
    db.close()
    started = client.post(
        "/unified/start",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={"csrf": csrf, "source_type": "own-game", "version": VERSION, "key": str(evidence)},
    )
    assert started.status_code == 303
    page = client.get(
        started.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert page.status_code == 200 and b"b5d6" not in page.data and b"b5c7" not in page.data
    assert (
        b"piece on b5" in page.data
        and b"piece on e8" in page.data
        and b"source missed" in page.data
    )
    attempt = token(page, "attempt")
    moved = client.post(
        "/unified/move",
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data={"csrf": csrf, "attempt": attempt, "event": token(page, "event"), "move": "b5d6"},
    )
    assert moved.status_code == 303
    db = Database(path)
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    db.close()
    result = client.get(
        moved.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert b"named fork and bounded material gain are proved" in result.data
