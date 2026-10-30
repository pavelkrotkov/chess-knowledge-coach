"""Assert stale diagnostics retain only their immutable attempt summary."""

from chess_coach.purpose_view import show
from tests.test_deep_selection import LEARNER


def assert_stale_attempt(db, request_id, status, detail):
    result = show(db, request_id, LEARNER)
    assert result["source_state"] == "stale"
    assert result["attempts"] == [{"number": 1, "status": status, "detail": detail}]
