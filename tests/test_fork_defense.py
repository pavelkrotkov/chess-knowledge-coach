"""Synthetic fork-defense witnesses preserve legal history and uncertainty."""

import chess
import pytest

from chess_coach.fork_defense_observation import observe
from chess_coach.fork_defense_probe import hypothetical


def mirror(uci):
    move = chess.Move.from_uci(uci)
    return chess.Move(
        chess.square_mirror(move.from_square), chess.square_mirror(move.to_square)
    ).uci()


def line(moves, score):
    return {
        "status": "limited",
        "score_kind": "cp",
        "score_bound": "exact",
        "score_value": score,
        "pv": " ".join(moves),
        "root_move": moves[0],
    }


@pytest.mark.parametrize("black", [False, True])
def test_existing_fork_threat_safe_alternatives_and_actual_failure(black):
    board = chess.Board("7k/6p1/8/8/1n6/8/7P/R3K3 w - - 0 1")
    best = ["a1b1", "h8g8", "e1f1", "g7g6"]
    other = ["e1f1", "h8g8", "a1b1", "g7g6"]
    played = ["h2h3", "b4c2", "e1f1", "c2a1"]
    if black:
        board = board.mirror()
        best, other, played = [list(map(mirror, moves)) for moves in (best, other, played)]
    assert board.is_valid()
    b, p = line(best, 500), line(played, 0)
    success = observe(board, best[0], b, b)
    assert success["outcome"] == "success"
    witness = success["threats"][0]
    assert witness["move"] in [move.uci() for move in board.legal_moves]
    after = board.copy()
    after.push_uci(witness["move"])
    assert chess.Move.from_uci(witness["fork"]["move"]) in after.legal_moves
    equivalent = observe(board, other[0], b, line(other, 400))
    assert equivalent["outcome"] == "success"
    failure = observe(board, played[0], b, p)
    assert failure["outcome"] == "failure" and failure["threat_origin"] == "existing"
    assert failure["played"]["material_delta"] == -5
    assert observe(board, played[0], b, {**p, "score_value": 400})["outcome"] == "ambiguous"


@pytest.mark.parametrize("black", [False, True])
def test_played_move_can_create_a_fork_with_verified_legal_defense(black):
    board = chess.Board("7k/6p1/8/8/1n6/8/7P/1R2K3 w - - 0 1")
    best = ["b1b3", "h8g8", "e1f1", "g7g6"]
    played = ["b1a1", "b4c2", "e1f1", "c2a1"]
    if black:
        board = board.mirror()
        best, played = [list(map(mirror, moves)) for moves in (best, played)]
    assert hypothetical(board) == {}
    result = observe(board, played[0], line(best, 500), line(played, 0))
    assert result["outcome"] == "failure" and result["threat_origin"] == "created_by_played_move"


def test_direct_material_loss_and_countercheck_are_not_falsely_called_safe():
    board = chess.Board("7k/6p1/8/8/1n6/8/7P/R3K3 w - - 0 1")
    best = line(["a1b1", "h8g8", "e1f1", "g7g6"], 500)
    material_loss = observe(board, "a1a2", best, line(["a1a2", "h8g8"], 0))
    assert (
        material_loss["outcome"] == "ambiguous"
        and material_loss["reason"] == "post_move_material_threat"
    )
    countercheck = observe(board, "a1a8", best, line(["a1a8", "h8g7"], 0))
    assert (
        countercheck["outcome"] == "ambiguous"
        and countercheck["reason"] == "forcing_defense_unresolved"
    )


def test_pinned_attacker_and_no_opportunity_do_not_create_outcomes():
    board = chess.Board("1k6/6p1/8/8/1n6/8/7P/RR2K3 w - - 0 1")
    assert board.is_valid() and hypothetical(board) == {}
    played = line(["e1f1", "b8c8"], 0)
    assert observe(board, "e1f1", played, played) is None


def test_hypothetical_is_only_a_positional_filter_and_anchor_keeps_real_history(monkeypatch):
    from chess_coach import fork_defense_anchor, fork_defense_anchor_match

    board = chess.Board("7k/6p1/8/3n4/8/8/7P/R3K3 b - - 0 1")
    board.push_uci("d5b4")
    before_fen, before_stack = board.fen(), list(board.move_stack)
    candidates = hypothetical(board)
    assert candidates and (board.fen(), board.move_stack) == (before_fen, before_stack)
    original = fork_defense_anchor_match.fork_proof
    checked = []

    def proof_with_history(actual, move):
        assert len(actual.move_stack) == len(before_stack) + 1
        checked.append(True)
        return original(actual, move)

    monkeypatch.setattr(fork_defense_anchor_match, "fork_proof", proof_with_history)
    witness = fork_defense_anchor.anchor(board, candidates)
    assert checked and witness and (board.fen(), board.move_stack) == (before_fen, before_stack)


def test_null_or_illegal_played_move_is_never_a_game_branch():
    board = chess.Board("7k/6p1/8/8/1n6/8/7P/R3K3 w - - 0 1")
    for move in ("0000", "e1e8"):
        result = observe(board, move, {}, {})
        assert result["outcome"] == "ambiguous" and result["reason"] == "invalid_played_move"


def test_score_gap_and_nonfork_reply_do_not_create_failure():
    board = chess.Board("7k/6p1/8/8/1n6/8/7P/R3K3 w - - 0 1")
    best = line(["a1b1", "h8g8", "e1f1", "g7g6"], 500)
    played = line(["h2h3", "h8g8", "e1f1", "g7g6"], 0)
    result = observe(board, "h2h3", best, played)
    assert result["outcome"] == "ambiguous" and result["reason"] == "recorded_fork_unverified"


def test_exhausted_anchor_budget_does_not_claim_prevention(monkeypatch):
    from chess_coach import fork_defense_anchor

    board = chess.Board("7k/6p1/8/8/1n6/8/7P/R3K3 w - - 0 1")
    best = line(["a1b1", "h8g8", "e1f1", "g7g6"], 500)
    monkeypatch.setattr(fork_defense_anchor, "MAX_ANCHOR_MOVES", 0)
    result = observe(board, "a1b1", best, best)
    assert result["outcome"] == "ambiguous" and result["reason"] == "anchor_move_budget_exhausted"


def test_real_repetition_history_blocks_counterfactual_outcome():
    board = chess.Board("7k/6p1/8/8/1n6/8/7P/R3K3 w - - 0 1")
    for move in ("e1f1", "h8g8", "f1e1", "g8h8"):
        board.push_uci(move)
    assert board.is_repetition(2)
    best = line(["a1b1", "h8g8", "e1f1", "g7g6"], 500)
    result = observe(board, "a1b1", best, best)
    assert result["outcome"] == "ambiguous" and result["reason"] == "hypothetical_probe_unavailable"
