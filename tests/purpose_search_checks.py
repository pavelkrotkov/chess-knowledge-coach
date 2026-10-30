"""Verify played-root and full-history synthetic search inputs."""

import chess

from chess_coach.purpose_view import show
from tests.test_deep_selection import LEARNER


def assert_black_history(engine):
    assert engine.calls[1][3][0].uci() == "e7e5"
    assert [move.uci() for move in engine.calls[0][0].move_stack] == ["e2e4"]
    assert engine.calls[1][0].move_stack == engine.calls[0][0].move_stack


def assert_scout_outside_played(engine, db, request_id):
    scout, final = engine.calls
    assert scout[3] is None
    assert final[3][0].uci() == "e2e4"
    assert len(set(final[3])) == 2
    attempt = show(db, request_id, LEARNER)["attempts"][0]
    assert attempt["final"]["comparison_issue"] is None


def forced_reply_board():
    board = chess.Board("6k1/5Q2/6K1/8/8/8/8/8 b - - 0 1")
    assert board.is_valid()
    assert board.is_check()
    assert board.legal_moves.count() == 1
    return board


def install_repeated_history(monkeypatch):
    import tests.test_deep_selection as fixture

    repeated = fixture.PGN.replace(
        "1. e4 e5 2. Nf3 Nc6 3. Bc4 Nf6 4. d3 d6 5. c3 Be7 6. O-O O-O *",
        "1. Nf3 Nf6 2. Ng1 Ng8 3. Nf3 Nf6 4. Ng1 Ng8 *",
    )
    monkeypatch.setattr(fixture, "PGN", repeated)
