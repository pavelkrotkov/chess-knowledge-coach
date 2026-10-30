"""Exercise promoted training continuation and assistance."""

import chess
import pytest

from chess_coach.unified_session_events import hint, reveal, show, submit
from tests.test_objective_promotion import SUBJECT
from tests.test_objective_promotion_proof_safety import proved_source


@pytest.mark.parametrize("assistance", ["hint", "reveal"])
def test_forced_promotion_continuation_records_assistance(tmp_path, assistance):
    db, _, _, _, _ = proved_source(tmp_path)
    action = {"hint": hint, "reveal": reveal}[assistance]
    response = action(db, "proof", SUBJECT, event_id="assist")
    assert response["assistance_kind"] == {"hint": "hinted", "reveal": "revealed"}[assistance]
    assert action(db, "proof", SUBJECT, event_id="assist") == response
    board = chess.Board(show(db, "proof", SUBJECT)["fen"])
    move = next(move for move in board.legal_moves if move.promotion == chess.KNIGHT)
    assert (
        submit(db, "proof", SUBJECT, event_id="final", move=move.uci())["status"]
        == "objective_verified"
    )


@pytest.mark.parametrize("legal", [False, True])
def test_forced_continuation_rejects_invalid_or_nonpromoting_moves(tmp_path, legal):
    db, _, _, _, _ = proved_source(tmp_path)
    board = chess.Board(show(db, "proof", SUBJECT)["fen"])
    move = next(move.uci() for move in board.legal_moves if not move.promotion) if legal else "a1a2"
    result = submit(db, "proof", SUBJECT, event_id="final", move=move)
    assert result["feedback"] == ("incorrect" if legal else "illegal")
    if not legal:
        assert show(db, "proof", SUBJECT)["promotion_continuation"]
