"""Synthetic bounded fork proof and outcome examples."""

import chess
import pytest

from chess_coach.fork_observation import observe
from chess_coach.fork_proof import fork_proof


def line(*moves, score=0):
    return {
        "status": "limited",
        "score_kind": "cp",
        "score_bound": "exact",
        "score_value": score,
        "pv": " ".join(moves),
        "root_move": moves[0],
    }


def mirror(uci):
    move = chess.Move.from_uci(uci)
    return chess.Move(
        chess.square_mirror(move.from_square),
        chess.square_mirror(move.to_square),
        promotion=move.promotion,
    ).uci()


@pytest.mark.parametrize("black", [False, True])
def test_checking_knight_fork_has_witness_for_every_legal_evasion(black):
    board = chess.Board("r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1")
    if black:
        board = board.mirror()
    played = mirror("b5c7") if black else "b5c7"
    reply = mirror("e8f8") if black else "e8f8"
    proof = fork_proof(board, chess.Move.from_uci(played))
    assert proof and len(proof["branches"]) == proof["legal_replies"] == 5
    result = observe(board, played, None, line(played, reply))
    assert result["outcome"] == "success" and result["proof"] == proof


def test_pseudo_fork_with_recapturable_rook_is_not_supported():
    board = chess.Board("r3k3/7p/1b6/1N6/8/8/6P1/7K w - - 0 1")
    assert board.is_valid()
    move = chess.Move.from_uci("b5c7")
    assert move in board.legal_moves
    assert fork_proof(board, move) is None
    result = observe(board, move.uci(), None, line("b5c7", "e8f8"))
    assert result["outcome"] == "ambiguous"


@pytest.mark.parametrize("black", [False, True])
def test_missed_fork_requires_material_and_score_veto(black):
    board = chess.Board("r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1")
    best_moves = ("b5c7", "e8f8", "c7a8", "h7h6")
    played_moves = ("h1g1", "e8f8", "b5c7", "h7h6")
    if black:
        board = board.mirror()
        best_moves = tuple(map(mirror, best_moves))
        played_moves = tuple(map(mirror, played_moves))
    best, played = line(*best_moves, score=600), line(*played_moves, score=0)
    result = observe(board, played_moves[0], best, played)
    assert result["outcome"] == "failure" and result["proof"]["move"] == best_moves[0]
    equivalent = {**played, "score_value": 500}
    assert observe(board, played_moves[0], best, equivalent)["outcome"] == "ambiguous"


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize(
    ("fen", "move"),
    [
        ("8/p6R/3r1k2/8/2N1P3/1B6/2B5/K7 w - - 0 1", "e4e5"),
        ("8/7k/2p3b1/K7/8/1Q6/6r1/8 w - - 0 1", "b3h3"),
        ("2k2N2/BN6/B1n1n2p/5B2/2K5/8/8/2R5 w - - 0 1", "c4d5"),
    ],
)
def test_pawn_queen_and_king_forks_have_legal_bounded_witnesses(fen, move, black):
    board = chess.Board(fen)
    if black:
        board, move = board.mirror(), mirror(move)
    assert board.is_valid()
    proof = fork_proof(board, chess.Move.from_uci(move))
    assert proof and proof["branches"] and proof["minimum_gain"] == 3
    for branch in proof["branches"]:
        after = board.copy()
        after.push_uci(move)
        assert chess.Move.from_uci(branch["reply"]) in after.legal_moves
        after.push_uci(branch["reply"])
        assert chess.Move.from_uci(branch["capture"]) in after.legal_moves


def test_exhausted_reply_budget_cannot_produce_a_fork(monkeypatch):
    from chess_coach import fork_proof as proof_module

    board = chess.Board("r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1")
    monkeypatch.setattr(proof_module, "MAX_REPLIES", 0)
    assert proof_module.fork_proof(board, chess.Move.from_uci("b5c7")) is None


def test_missing_best_source_is_ambiguous_even_without_played_fork():
    board = chess.Board("r3k3/7p/8/1N6/8/8/6P1/7K w - - 0 1")
    result = observe(board, "h1g1", None, line("h1g1", "e8f8"))
    assert result["outcome"] == "ambiguous" and result["reason"] == "current_best_unavailable"


@pytest.mark.parametrize("black", [False, True])
def test_capturing_defense_requires_gain_from_original_position(black):
    from chess_coach.fork_branch import defense_witness
    from chess_coach.material_lines import material

    board = chess.Board("8/2P5/8/6K1/8/6br/1k3N2/3r4 b - - 0 1")
    if black:
        board = board.mirror()
    transform = mirror if black else lambda move: move
    attacker = chess.parse_square(transform("f2d1")[:2])
    targets = tuple(chess.parse_square(transform(move)[2:]) for move in ("f2d1", "f2h3"))
    reply = chess.Move.from_uci(transform("g3c7"))
    color = not board.turn
    initial = material(board, color)
    assert board.is_valid() and board.is_capture(reply)
    assert defense_witness(board, reply, attacker, targets, color, initial)
    board.set_piece_at(chess.parse_square(transform("g3c7")[2:]), chess.Piece(chess.ROOK, color))
    assert defense_witness(board, reply, attacker, targets, color, material(board, color)) is None


def test_counterreply_uses_material_before_the_defensive_capture():
    from chess_coach.material_lines import material
    from chess_coach.material_reply_guard import _unresolved

    board = chess.Board("8/2R5/8/6K1/8/6bq/1k1B1N2/3r4 b - - 0 1")
    assert board.is_valid()
    original = material(board, chess.WHITE)
    board.push_uci("g3c7")
    pre_capture = material(board, chess.WHITE)
    board.push_uci("f2h3")
    reply = chess.Move.from_uci("d1d2")
    assert reply in board.legal_moves and board.is_capture(reply)
    assert not _unresolved(board, reply, chess.WHITE, pre_capture)
    assert _unresolved(board, reply, chess.WHITE, original)


@pytest.mark.parametrize("black", [False, True])
@pytest.mark.parametrize(
    ("fen", "move"),
    [
        ("r3k3/2p4p/8/1N6/8/8/6P1/7K w - - 0 1", "b5c7"),
        ("1r6/6Pk/8/8/8/8/8/K7 w - - 0 1", "g7g8q"),
        ("7k/2r1r3/8/3pP3/8/8/8/K7 w - d6 0 1", "e5d6"),
    ],
)
def test_unsupported_legal_fork_shapes_are_ambiguous(fen, move, black):
    board = chess.Board(fen)
    if black:
        board, move = board.mirror(), mirror(move)
    assert board.is_valid() and chess.Move.from_uci(move) in board.legal_moves
    result = observe(board, move, None, None)
    assert result == {"kind": "fork", "outcome": "ambiguous", "reason": "unsupported_fork_move"}
    assert fork_proof(board, chess.Move.from_uci(move)) is None


def test_unsupported_best_shape_cannot_be_graded_as_missed_fork():
    board = chess.Board("r3k3/2p4p/8/1N6/8/8/6P1/7K w - - 0 1")
    result = observe(board, "h1g1", line("b5c7", "e8f8"), line("h1g1", "e8f8"))
    assert result["outcome"] == "ambiguous" and result["reason"] == "unsupported_fork_move"


@pytest.mark.parametrize("black", [False, True])
def test_fork_proof_includes_profitable_capturing_defense(black):
    board = chess.Board("q3k3/5N1p/8/1N6/8/8/6P1/7K w - - 0 1")
    move, reply = "b5c7", "e8f7"
    if black:
        board, move, reply = board.mirror(), mirror(move), mirror(reply)
    proof = fork_proof(board, chess.Move.from_uci(move))
    assert board.is_valid() and proof
    assert any(branch["reply"] == reply for branch in proof["branches"])
    assert observe(board, move, None, line(move, reply))["outcome"] == "success"
    queen = chess.parse_square(mirror("b5a8")[2:] if black else "a8")
    board.set_piece_at(queen, chess.Piece(chess.ROOK, not board.turn))
    assert fork_proof(board, chess.Move.from_uci(move)) is None
