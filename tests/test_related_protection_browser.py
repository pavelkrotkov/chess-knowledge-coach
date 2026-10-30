"""Evidence and CLI entry points open protected defensive practice."""

from chess_coach.related_protection import preview
from chess_coach.web import create_app
from tests.related_protection_support import assert_protection_page, source_and_corpus
from tests.test_material_pipeline import LEARNER
from tests.test_unified_sessions import token


def test_browser_evidence_preview_csrf_and_start(tmp_path, monkeypatch):
    path = tmp_path / "browser.sqlite"
    db, evidence = source_and_corpus(path, monkeypatch)
    expected = preview(db, LEARNER, evidence, "test")["items"][0]["reference"]
    db.close()
    monkeypatch.setattr(
        "chess_coach.web_security.secrets.token_urlsafe",
        lambda size: "A" * (43 if size == 32 else 32),
    )
    app = create_app(
        db_path=path,
        subject=LEARNER,
        actor="fixture",
        corpus="test",
        login="fixture",
        origin="https://coach.invalid",
    )
    client = app.test_client()
    headers = {"Tailscale-User-Login": "fixture"}
    source = client.get(f"/evidence/{evidence}", base_url="https://coach.invalid", headers=headers)
    assert source.status_code == 200 and b"Find related protection practice" in source.data
    page = client.get(
        f"/evidence/{evidence}/related-protections",
        base_url="https://coach.invalid",
        headers=headers,
    )
    with client.session_transaction(base_url="https://coach.invalid") as session:
        csrf = session["csrf"]
    assert token(page, "reference") == expected
    assert_protection_page(page, csrf, expected)
    data = {"csrf": csrf, "reference": expected}
    url = f"/evidence/{evidence}/related-protections/start"
    assert (
        client.post(url, base_url="https://coach.invalid", headers=headers, data=data).status_code
        == 403
    )
    result = client.post(
        url,
        base_url="https://coach.invalid",
        headers=headers | {"Origin": "https://coach.invalid"},
        data=data,
    )
    assert result.status_code == 303
    practice = client.get(
        result.headers["Location"], base_url="https://coach.invalid", headers=headers
    )
    assert_protection_page(practice, csrf)
