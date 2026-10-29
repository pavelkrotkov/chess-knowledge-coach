"""Synthetic positions for legal pin geometry and bounded material proof."""

import chess
import pytest

from chess_coach.pin_geometry import pins
from chess_coach.pin_observation import observe
from chess_coach.pin_proof import proven


@pytest.mark.parametrize("mirror", [False, True])
def test_absolute_pin_requires_all_legal_replies(mirror):
    board = chess.Board("2k5/3r1N2/N1n1B2p/3P4/1R6/8/8/1R1K4 w - - 0 1")
    move = chess.Move.from_uci("b4c4")
    if mirror:
        board = board.mirror()
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    result = observe(board, move.uci(), None, None)
    assert result["outcome"] == "success"
    witness = result["proof"]
    assert witness["type"] == "absolute_pin"
    after = board.copy()
    after.push(move)
    assert {branch["reply"] for branch in witness["branches"]} == {
        m.uci() for m in after.legal_moves
    }
    assert all(branch["mate"] for branch in witness["branches"])


def test_relative_pin_geometry_is_not_a_proven_gain():
    board = chess.Board("4r2k/p1p1pppp/B1n5/3P4/8/8/8/2K5 w - - 0 1")
    move = board.parse_uci("a6b5")
    assert pins(board, move)[0]["type"] == "relative_pin"
    assert not proven(board, move)
    assert observe(board, move.uci(), None, None)["outcome"] == "ambiguous"


def test_defended_pinned_piece_does_not_become_a_material_claim():
    board = chess.Board("4k3/1p6/B1n5/3P4/8/8/8/4K3 w - - 0 1")
    move = board.parse_uci("a6b5")
    assert pins(board, move)
    assert not proven(board, move)
    assert observe(board, move.uci(), None, None)["outcome"] == "ambiguous"


@pytest.mark.parametrize("mirror", [False, True])
def test_relative_pin_exposure_and_capture_defense(mirror):
    from chess_coach.pin_defense import observe as prevent

    board = chess.Board("7k/5p2/8/8/8/4r3/4R2K/4Q3 w - - 0 1")
    bad = chess.Move.from_uci("e2f2")
    good = chess.Move.from_uci("e2e3")
    if mirror:
        board = board.mirror()
        bad = chess.Move(chess.square_mirror(bad.from_square), chess.square_mirror(bad.to_square))
        good = chess.Move(
            chess.square_mirror(good.from_square), chess.square_mirror(good.to_square)
        )
    failed = prevent(board, bad.uci(), None, None)
    assert failed["kind"] == "relative_pin" and failed["outcome"] == "failure"
    assert failed["proof"]["mode"] == "exposure" and failed["alternative"]["move"] == good.uci()
    succeeded = prevent(board, good.uci(), None, None)
    assert succeeded["kind"] == "relative_pin" and succeeded["outcome"] == "success"
    assert succeeded["proof"]["mode"] == "exposure"


def test_relative_exposure_without_verified_defense_is_ambiguous():
    from chess_coach.pin_defense import observe as prevent

    board = chess.Board("4r2k/8/8/8/8/8/4N2K/4Q3 w - - 0 1")
    result = prevent(board, "e2c1", None, None)
    assert result["kind"] == "relative_pin" and result["outcome"] == "ambiguous"


@pytest.mark.parametrize("mirror", [False, True])
def test_relative_pin_execution_proves_each_reply_including_piece_moves(mirror):
    board = chess.Board("4r2k/b1p5/Bpnppppp/8/8/8/8/7K w - - 0 1")
    move = chess.Move.from_uci("a6b5")
    if mirror:
        board = board.mirror()
        move = chess.Move(
            chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
        )
    result = observe(board, move.uci(), None, None)
    assert result["kind"] == "relative_pin" and result["outcome"] == "success"
    after = board.copy()
    after.push(move)
    pinned = chess.parse_square(result["proof"]["pinned"])
    replies = {branch["reply"] for branch in result["proof"]["branches"]}
    assert replies == {reply.uci() for reply in after.legal_moves}
    assert any(chess.Move.from_uci(reply).from_square == pinned for reply in replies)


def test_equivalent_defenses_are_observed_without_engine_preference():
    from chess_coach.pin_defense import observe as prevent

    board = chess.Board("7k/5p2/8/8/8/4r3/4R2K/3NQ3 w - - 0 1")
    assert prevent(board, "e2e3", None, None)["outcome"] == "success"
    assert prevent(board, "d1e3", None, None)["outcome"] == "success"


def test_intervening_check_is_not_scored_as_an_exposed_capture():
    from chess_coach.pin_defense import observe as prevent

    board = chess.Board("8/5p2/8/8/5k2/4r3/4R2K/4Q3 w - - 0 1")
    assert board.gives_check(board.parse_uci("e2f2"))
    assert prevent(board, "e2f2", None, None)["outcome"] == "ambiguous"


def test_recapturable_pinner_does_not_prove_a_defensive_alternative():
    from chess_coach.pin_defense import observe as prevent

    board = chess.Board("7k/5p2/8/8/3p4/4r3/4R2K/4Q3 w - - 0 1")
    result = prevent(board, "e2f2", None, None)
    assert result["outcome"] == "ambiguous"
    assert result["reason"] == "alternative_defense_unverified"
    assert result["proof"]["san"] == "Rxe1"


def test_checking_counterplay_does_not_prove_exposure_loss():
    from chess_coach.pin_defense import observe as prevent

    board = chess.Board("7k/8/8/8/8/4r3/4R2K/4Q3 w - - 0 1")
    result = prevent(board, "e2f2", None, None)
    assert result["outcome"] == "ambiguous"
    assert result["reason"] == "exposure_or_defense_unresolved"


def test_existing_pin_and_already_capturable_target_do_not_prove_creation():
    existing = chess.Board("4k3/8/2n5/3P4/B7/8/8/4K3 w - - 0 1")
    assert not pins(existing, existing.parse_uci("a4b5"))
    hanging = chess.Board("4k3/8/B1n5/3P4/8/8/8/4K3 w - - 0 1")
    result = observe(hanging, "a6b5", None, None)
    assert result["outcome"] == "ambiguous" and result["geometry"]["pinned"] == "c6"


def test_competing_mate_prevents_claim_of_absolute_pin_defense():
    from chess_coach.mate_proof_moves import immediate_mates
    from chess_coach.pin_defense import observe as prevent

    board = chess.Board("2k5/3r1N2/N1n1B2p/3P4/1R6/8/8/1R1K4 b - - 0 1")
    move = board.parse_uci("c6a5")
    after = board.copy()
    after.push(move)
    assert immediate_mates(after)
    result = prevent(board, move.uci(), None, None)
    assert result["outcome"] == "ambiguous"
    assert result["reason"] == "other_immediate_threat_unresolved"
    assert result["proof"]["type"] == "absolute_pin"


@pytest.mark.parametrize("mirror", [False, True])
def test_absolute_pin_slide_and_capture_defense(mirror):
    from chess_coach.pin_defense import observe as prevent

    board = chess.Board("7k/8/8/4r3/8/8/4R3/4K3 w - - 0 1")
    bad = chess.Move.from_uci("e2e3")
    good = chess.Move.from_uci("e2e5")
    if mirror:
        board = board.mirror()
        bad = chess.Move(chess.square_mirror(bad.from_square), chess.square_mirror(bad.to_square))
        good = chess.Move(
            chess.square_mirror(good.from_square), chess.square_mirror(good.to_square)
        )
    failure = prevent(board, bad.uci(), None, None)
    success = prevent(board, good.uci(), None, None)
    assert failure["kind"] == success["kind"] == "absolute_pin"
    assert failure["outcome"] == "failure" and success["outcome"] == "success"
    assert failure["proof"]["mode"] == "pinned_capture"
    assert failure["alternative"]["move"] == good.uci()
