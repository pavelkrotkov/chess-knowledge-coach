"""A fork claim remains unknown outside the qualified proof contract."""

import chess

from chess_coach.objective_fork_judge import judge
from tests.objective_fork_support import FEN


def test_unproved_moves_and_changed_attacker_are_unresolved():
    board = chess.Board(FEN)
    anchor = chess.E8
    attacker = chess.B5
    other = judge(board, board.parse_uci("f6g5"), attacker, anchor, lambda: 0, 0, 5, {})
    assert (
        other["status"] == "unresolved" and other["reason"] == "named_attacker_or_move_unavailable"
    )
    quiet = judge(board, board.parse_uci("b5a3"), attacker, anchor, lambda: 0, 0, 5, {})
    assert quiet["status"] == "unresolved" and quiet["reason"] == "fork_or_consequence_unresolved"


def test_timeout_and_wrong_anchor_never_publish_a_proof():
    board = chess.Board(FEN)
    move = board.parse_uci("b5d6")
    assert judge(board, move, chess.B5, chess.E8, lambda: 6, 0, 5, {})["reason"] == "timeout"
    result = judge(board, move, chess.B5, chess.A8, lambda: 0, 0, 5, {})
    assert result["status"] == "unresolved" and result["reason"] == "fork_or_consequence_unresolved"


def test_mirrored_black_alternative_uses_same_objective():
    board = chess.Board(FEN).mirror()
    move = board.parse_uci("b4d3")
    result = judge(board, move, chess.B4, chess.E1, lambda: 0, 0, 5, {})
    assert result["status"] == "correct" and result["proven_gain_floor"] == 3


def test_expired_proof_and_invalid_bound_stay_unresolved():
    from chess_coach.objective_fork_verify import verify

    board = chess.Board(FEN)
    move = board.parse_uci("b5d6")
    ticks = iter((0.0, 6.0))
    result = judge(board, move, chess.B5, chess.E8, lambda: next(ticks), 0, 5, {})
    assert result["status"] == "unresolved" and result["reason"] == "timeout"
    data = {"fork_attacker": "b5", "fork_anchor": "e8", "gain_threshold": 3.0}
    result = verify(board, move, {"learner_color": "white"}, [], lambda: 0, 0, 5, {}, data)
    assert result["status"] == "unresolved" and result["reason"] == "objective_binding_unavailable"
