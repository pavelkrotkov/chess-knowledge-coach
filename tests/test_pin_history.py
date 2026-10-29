"""Pin execution respects the full history at the original decision."""

import chess
import pytest

from chess_coach.pin_observation import observe
from chess_coach.pin_proof_eligibility import eligible

FEN = "4r2k/b1p5/Bpnppppp/8/8/8/8/7K w - - 0 1"
CYCLE = ("h1g1", "h8g8", "g1h1", "g8h8")


def position(mirror, cycles=0, halfmove=None):
    board = chess.Board(FEN)
    if mirror:
        board = board.mirror()
    for _ in range(cycles):
        for text in CYCLE:
            move = chess.Move.from_uci(text)
            if mirror:
                move = chess.Move(
                    chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
                )
            assert move in board.legal_moves
            board.push(move)
    if halfmove is not None:
        board.halfmove_clock = halfmove
    move = chess.Move.from_uci("a6b5")
    if mirror:
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    return board, move


@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("cycles", [1, 2, 4])
def test_repeated_root_does_not_prove_pin(mirror, cycles):
    board, move = position(mirror, cycles)
    assert board.is_repetition(2)
    assert board.is_repetition(3) == (cycles >= 2)
    assert board.is_fivefold_repetition() == (cycles == 4)
    assert eligible(board, move) is False
    assert observe(board, move.uci(), None, None)["outcome"] == "ambiguous"


@pytest.mark.parametrize("mirror", [False, True])
@pytest.mark.parametrize("halfmove", [100, 150])
def test_draw_clock_at_root_does_not_prove_pin(mirror, halfmove):
    board, move = position(mirror, halfmove=halfmove)
    assert board.is_fifty_moves()
    assert board.is_game_over() == (halfmove == 150)
    assert eligible(board, move) is False
    assert observe(board, move.uci(), None, None)["outcome"] == "ambiguous"


@pytest.mark.parametrize("mirror", [False, True])
def test_fresh_history_still_proves_pin(mirror):
    board, move = position(mirror)
    assert eligible(board, move)
    assert observe(board, move.uci(), None, None)["outcome"] == "success"
