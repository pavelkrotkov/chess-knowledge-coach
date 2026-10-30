"""Synthetic material exchanges honor legal and bounded semantics."""

import chess

from chess_coach.material_exchange import exchange


def test_legal_capture_gain_and_defended_exchange():
    loose = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    assert loose.is_valid()
    assert exchange(loose, chess.Move.from_uci("d1d4")) == 9
    defended = chess.Board("4k3/8/8/2p5/3q4/8/8/3RK3 w - - 0 1")
    assert defended.is_valid()
    assert exchange(defended, chess.Move.from_uci("d1d4")) == 4


def line(moves):
    return {
        "status": "limited",
        "score_kind": "cp",
        "score_value": 0,
        "score_bound": "exact",
        "pv": " ".join(moves),
        "root_move": moves[0],
    }


def test_recorded_capture_and_missed_capture_are_bounded_observations():
    from chess_coach.material_observation import material_observation

    board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    best = {**line(["d1d4", "e8f8"]), "score_value": 500}
    played = line(["e1f1", "e8f8"])
    missed = material_observation(board, "e1f1", best, played)
    assert missed["outcome"] == "failure" and missed["target"] == "d4"
    assert missed["best"]["san"] == ["Rxd4", "Kf8"]
    assert missed["exchange_gain"] == 9 and "only" in missed["boundary"]
    taken = material_observation(board, "d1d4", best, best)
    assert taken["outcome"] == "success"


def test_material_protection_and_exposed_loss_are_observed():
    from chess_coach.material_observation import material_observation

    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")
    assert board.is_valid()
    best = {**line(["d4d5", "e8f8"]), "score_value": 500}
    protected = material_observation(board, "d4d5", best, best)
    assert protected["kind"] == "material_protection" and protected["outcome"] == "success"
    assert protected["target"] == "d5" and "hypothetical" in protected["boundary"]
    played = line(["a2a3", "c5d4"])
    missed = material_observation(board, "a2a3", best, played)
    assert missed["kind"] == "material_protection" and missed["outcome"] == "failure"
    assert missed["played"]["san"][1] == "Bxd4"
