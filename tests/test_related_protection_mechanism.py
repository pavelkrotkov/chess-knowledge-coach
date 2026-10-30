"""Only supported specified-piece defenses enter transfer matching."""

import chess
import pytest

from chess_coach.puzzle_session_validate import validate_line
from chess_coach.related_protection_features import protection_features
from tests.test_objective_protection import oriented


@pytest.mark.parametrize("black", [False, True])
def test_capture_of_the_proved_attacker_can_be_a_defense(black):
    board = chess.Board("4k3/8/8/R1b5/3R4/8/P7/7K w - - 0 1")
    if black:
        board = board.mirror()
    features = protection_features(board.fen(), [oriented("a5c5", black)])
    assert features is not None and features["target_square"] == ("d5" if black else "d4")


def test_unrelated_attacking_capture_is_not_a_protection_example():
    board = chess.Board("4k3/8/p7/R1b5/3R4/8/P7/7K w - - 0 1")
    move = board.parse_uci("a5a6")
    assert board.is_capture(move)
    assert protection_features(board.fen(), [move.uci()]) is None


def test_malformed_line_or_unknown_prior_history_is_not_qualified():
    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")
    assert protection_features(board.fen(), ["d4d3", "e8e6"]) is None
    board.halfmove_clock = 5
    assert protection_features(board.fen(), ["d4d3"]) is None


def test_setup_replay_preserves_castling_rights_and_learner_side():
    fen = "r3k2r/7p/8/2b5/3R4/8/PP6/4K2R b Kkq - 0 1"
    prompt = validate_line(fen, "h7h6 d4d3 e8f8 d3d2")
    board = chess.Board(prompt)
    assert board.turn == chess.WHITE and board.castling_xfen() == "Kkq"
    assert board.halfmove_clock == 0
