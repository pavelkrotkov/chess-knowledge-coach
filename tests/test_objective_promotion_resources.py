"""Bound promotion proof resource use and legal replies."""

import chess


def test_proof_deadline_and_size_limits_do_not_publish_success():
    from chess_coach.objective_promotion_result import classify

    proof = {"status": "proved", "witnesses": [{"reply": "x" * 65536}]}
    assert classify(proof, {}, 1, lambda: 0, 0, 5)["reason"] == "proof_size_limit"
    assert classify({"status": "proved"}, {}, 1, lambda: 6, 0, 5)["reason"] == "timeout"


def test_excessive_opponent_reply_count_is_unresolved(monkeypatch):
    from chess_coach import objective_promotion_scan
    from chess_coach.objective_promotion_contract import FORCE
    from chess_coach.objective_promotion_judge import judge

    board = chess.Board("7k/8/P1K5/8/8/8/8/8 w - - 0 1")
    monkeypatch.setattr(objective_promotion_scan, "MAX_REPLIES", 0)
    result = judge(board, board.parse_uci("a6a7"), FORCE, lambda: 0, 0, 5, {})
    assert result["status"] == "unresolved" and result["reason"] == "reply_limit"


def test_legal_defense_refutes_promotion_within_two_moves():
    from chess_coach.objective_promotion_contract import FORCE
    from chess_coach.objective_promotion_judge import judge

    board = chess.Board("8/8/8/8/8/2K5/P7/1k6 w - - 0 1")
    move = board.parse_uci("a2a3")
    result = judge(board, move, FORCE, lambda: 0, 0, 5, {})
    assert result["status"] == "incorrect" and result["reason"] == "no_legal_promotion"
    board.push(move)
    reply = board.parse_uci(result["proof"]["reply"])
    assert reply in board.legal_moves
    board.push(reply)
    assert not any(candidate.promotion for candidate in board.legal_moves)
