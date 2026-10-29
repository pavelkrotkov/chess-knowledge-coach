"""Explicit promotion goals reject unsupported and terminal positions."""

import chess

from chess_coach.objective_promotion_contract import FORCE, NOW
from chess_coach.objective_promotion_judge import judge


def test_quiet_move_cannot_satisfy_immediate_promotion():
    board = chess.Board("7k/8/P1K5/8/8/8/8/8 w - - 0 1")
    result = judge(board, board.parse_uci("a6a7"), NOW, lambda: 0, 0, 5, {})
    assert result["status"] == "incorrect" and result["reason"] == "not_immediate_promotion"


def test_unknown_goal_and_illegal_move_are_unresolved():
    board = chess.Board("7k/8/P1K5/8/8/8/8/8 w - - 0 1")
    result = judge(board, chess.Move.from_uci("a6a7"), "promotion", lambda: 0, 0, 5, {})
    assert result["status"] == "unresolved" and result["reason"] == "unsupported_objective"
    result = judge(board, chess.Move.from_uci("a1a2"), FORCE, lambda: 0, 0, 5, {})
    assert result["status"] == "unresolved" and result["reason"] == "terminal_or_illegal_move"


def test_checkmate_before_promotion_does_not_prove_promotion():
    board = chess.Board("7k/5K2/6Q1/8/8/8/P7/8 w - - 0 1")
    result = judge(board, board.parse_uci("g6g7"), FORCE, lambda: 0, 0, 5, {})
    assert result["status"] == "incorrect" and result["reason"] == "terminal_before_promotion"
