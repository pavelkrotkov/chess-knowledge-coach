"""Synthetic purpose diagnostic coverage."""

import pytest

from chess_coach.purpose_view import show
from chess_coach.purpose_worker import run
from tests.purpose_fixtures import configure, request
from tests.purpose_search_checks import assert_scout_outside_played, forced_reply_board
from tests.test_deep_selection import LEARNER, setup_game


@pytest.mark.parametrize("mode", ["timeout", "short", "mate", "depth", "bound", "missing"])
def test_unusable_native_output_never_qualifies(tmp_path, monkeypatch, mode):
    db = setup_game(tmp_path / "unknown.sqlite", monkeypatch)
    request_id = request(db)
    engine = configure(monkeypatch, db, mode)
    outcome = run(db, request_id, LEARNER)
    assert outcome["status"] == "insufficient" and engine.closed
    assert len(engine.calls) <= 2
    assert show(db, request_id, LEARNER)["attempts"][0]["status"] == "insufficient"


def test_played_root_outside_scout_still_uses_one_restricted_final_search(tmp_path, monkeypatch):
    db = setup_game(tmp_path / "played-outside-scout.sqlite", monkeypatch)
    request_id = request(db)
    engine = configure(monkeypatch, db, mode="scout_without_played")
    outcome = run(db, request_id, LEARNER)
    assert outcome["status"] == "complete" and len(engine.calls) == 2
    assert_scout_outside_played(engine, db, request_id)


def test_forced_root_is_unknown_without_starting_search(monkeypatch):
    import chess_coach.purpose_search as search

    board = forced_reply_board()
    monkeypatch.setattr(search, "scout", lambda *_args: pytest.fail("forced move searched"))
    result, issue = search.search(None, board, {"uci": next(iter(board.legal_moves)).uci()}, 99)
    assert issue == "forced_move" and result["global_best"] == "unknown"
