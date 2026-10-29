"""Synthetic legal regressions for bounded discovered attacks."""

import chess
import pytest

from chess_coach.discovery_geometry import discoveries
from chess_coach.discovery_observation import observe
from chess_coach.discovery_proof import prove

MATERIAL = "7q/8/3k3N/8/8/8/8/1K5R w - - 0 1"
MATE = "7k/8/5K1N/8/8/8/8/6RR w - - 0 1"


def line(move):
    return {"status": "limited", "root_move": move, "pv": move, "score_bound": "exact"}


@pytest.mark.parametrize("mirror", [False, True])
def test_forcing_discovery_and_double_check_mate(mirror):
    board = chess.Board(MATERIAL)
    mate = chess.Board(MATE)
    if mirror:
        board, mate = board.mirror(), mate.mirror()
    move = chess.Move.from_uci("h3f2" if mirror else "h6f7")
    material = prove(board, move)[0]
    assert material["target"] == ("h1" if mirror else "h8")
    assert material["legal_replies"] > 1
    assert material["minimum_gain"] == 3
    assert not material["double_check"]
    checkmate = prove(mate, move)[0]
    assert checkmate["double_check"] and checkmate["mate"]
    assert checkmate["slider"] == ("h8" if mirror else "h1")


def test_blocked_and_illegal_roots_never_prove():
    board = chess.Board(MATERIAL)
    board.set_piece_at(chess.H4, chess.Piece.from_symbol("P"))
    move = chess.Move.from_uci("h6f7")
    assert not discoveries(board, move)
    assert not prove(board, move)
    pinned = chess.Board("k3r3/8/8/8/8/8/4N3/4K2R w - - 0 1")
    assert not prove(pinned, chess.Move.from_uci("e2f4"))


def test_capture_may_reveal_a_concrete_attack():
    board = chess.Board(MATERIAL)
    board.set_piece_at(chess.F7, chess.Piece.from_symbol("p"))
    move = chess.Move.from_uci("h6f7")
    assert board.is_capture(move)
    assert prove(board, move)[0]["target"] == "h8"


def test_harmless_line_and_unverified_alternative_are_ambiguous():
    board = chess.Board("3k3q/8/7N/8/8/8/8/1K5R w - - 0 1")
    move = "h6f7"
    assert discoveries(board, chess.Move.from_uci(move))
    assert not prove(board, chess.Move.from_uci(move))
    assert observe(board, move, line(move), line(move))["outcome"] == "ambiguous"
    board = chess.Board(MATE)
    assert observe(board, "g1f1", line("h6f7"), line("g1f1"))["outcome"] == "failure"
    assert observe(board, "g1f1", line("h6f7"), None)["outcome"] == "ambiguous"


def test_claimable_draw_and_history_prevent_claims():
    board = chess.Board(MATERIAL)
    board.halfmove_clock = 99
    assert board.can_claim_fifty_moves()
    assert not prove(board, chess.Move.from_uci("h6f7"))
    board = chess.Board()
    for move in ("g1f3", "g8f6", "f3g1", "f6g8") * 2:
        board.push_uci(move)
    assert board.can_claim_threefold_repetition()
    assert not prove(board, chess.Move.from_uci("g1f3"))


def test_incidental_attack_does_not_claim_mate_by_the_mover():
    board = chess.Board("3k1N1q/8/1K5N/8/8/8/8/2R1R2R w - - 0 1")
    move = chess.Move.from_uci("h6f7")
    assert board.san(move) == "Nf7#"
    assert discoveries(board, move)
    assert not prove(board, move)
    assert observe(board, move.uci(), line(move.uci()), line(move.uci()))["outcome"] == "ambiguous"
