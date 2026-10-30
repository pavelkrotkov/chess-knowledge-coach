"""Latest pawn request outcomes control legal continuation."""

import chess
import pytest

from chess_coach.objective_worker import process
from chess_coach.unified_session_events import show, submit
from tests.pawn_latest_support import finish_request
from tests.test_objective_pawn import SUBJECT, begin, setup_game


@pytest.mark.parametrize("outcome", ["correct", "incorrect", "unresolved", "cancel"])
def test_latest_pawn_request_controls_continuation(tmp_path, monkeypatch, outcome):
    db, evidence = setup_game(tmp_path / "latest.sqlite", monkeypatch)
    begin(db, evidence, "pawn")
    first = submit(db, "pawn", SUBJECT, event_id="first", move="e3f3")
    assert process(db, SUBJECT)["outcomes"] == {"correct": 1}
    board = chess.Board(show(db, "pawn", SUBJECT)["fen"])
    move = next(iter(board.legal_moves)).uci()
    second = submit(db, "pawn", SUBJECT, event_id="second", move=move)
    pending = show(db, "pawn", SUBJECT)
    assert pending["verification"]["status"] == "pending"
    assert not pending.get("pawn_continuation")
    assert submit(db, "pawn", SUBJECT, event_id="second", move=move) == second
    assert submit(db, "pawn", SUBJECT, event_id="first", move="e3f3") == first
    expected = finish_request(db, monkeypatch, outcome, move)
    final = show(db, "pawn", SUBJECT)
    assert final["verification"]["status"] == expected
    assert bool(final.get("pawn_continuation")) == (outcome == "correct")
