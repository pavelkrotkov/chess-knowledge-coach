"""Verify diagnostic browser access and stated limitations."""

from tests.purpose_browser_fixtures import app, browser_get
from tests.test_deep_selection import OPPONENT


def assert_private_browser(path, request_id):
    client = app(path).test_client()
    page = browser_get(client, f"/purpose-analysis/{request_id}")
    assert page.status_code == 200 and b"not a global-best ranking" in page.data
    assert b"no evidence, review, mastery or defense qualification" in page.data
    assert browser_get(client, "/purpose-analysis").status_code == 200
    assert browser_get(client, f"/purpose-analysis/{request_id}", login="wrong").status_code == 403
    assert (
        browser_get(
            app(path, OPPONENT).test_client(), f"/purpose-analysis/{request_id}"
        ).status_code
        == 404
    )


def assert_stale_browser(path, request_id, *, detail=None):
    page = browser_get(app(path).test_client(), f"/purpose-analysis/{request_id}")
    assert page.status_code == 200
    if detail is not None:
        assert detail in page.data
    assert b"stored lines are withheld" in page.data
    assert b"Candidate rank" not in page.data
