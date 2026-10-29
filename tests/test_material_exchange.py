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


def test_checking_illegal_and_special_captures_are_not_proven():
    checking = chess.Board("4k3/8/8/8/3q4/8/8/4R1K1 w - - 0 1")
    assert exchange(checking, chess.Move.from_uci("e1e8")) is None
    pinned = chess.Board("k3r3/8/8/8/8/3qR3/8/4K3 w - - 0 1")
    assert exchange(pinned, chess.Move.from_uci("e3d3")) is None
    ep = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    assert exchange(ep, chess.Move.from_uci("e5d6")) is None


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


def test_material_observations_require_legal_complete_nonchecking_lines():
    from chess_coach.material_observation import material_observation

    board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    best = {**line(["d1d4", "e8f8"]), "score_value": 500}
    assert material_observation(board, "e1f1", best, line(["e1f1"]))["outcome"] == "ambiguous"
    assert (
        material_observation(board, "e1f1", {**best, "score_bound": "lower"}, best)["outcome"]
        == "ambiguous"
    )
    pinned = chess.Board("k3r3/8/8/8/8/3qR3/8/4K3 w - - 0 1")
    assert (
        material_observation(pinned, "e3e2", line(["e3d3", "a8b8"]), best)["reason"]
        == "illegal_or_pinned_root"
    )
    quiet = line(["e1f1", "e8f8"])
    no_threat = chess.Board("4k3/8/8/8/8/8/P7/4K3 w - - 0 1")
    assert material_observation(no_threat, "e1f1", quiet, quiet) is None


def test_material_capture_supports_black_perspective():
    from chess_coach.material_observation import material_observation

    board = chess.Board("3rk3/8/8/3Q4/8/8/8/4K3 b - - 0 1")
    assert board.is_valid()
    best = line(["d8d5", "e1f1"])
    result = material_observation(board, "d8d5", best, best)
    assert result["outcome"] == "success" and result["best"]["san"][0] == "Rxd5"


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


def test_protection_probe_refuses_invalid_turn_and_en_passant_history():
    from chess_coach.material_defense import defense_observation

    board = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    result = defense_observation(board, "e1f1", line(["e1f1", "e8f8"]), line(["e1f1", "e8f8"]))
    assert result["outcome"] == "ambiguous" and result["reason"] == "invalid_hypothetical_probe"


def test_recapture_and_compensation_are_not_reported_as_clear_outcomes():
    from chess_coach.material_observation import material_observation

    board = chess.Board("4k3/8/8/2p5/3q4/8/8/3RK3 w - - 0 1")
    best = {**line(["d1d4", "c5d4"]), "score_value": 500}
    result = material_observation(board, "d1d4", best, best)
    assert result["outcome"] == "ambiguous" and result["reason"] == "recapture_or_sacrifice"
    loose = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    best = line(["d1d4", "e8f8"])
    played = line(["e1f1", "e8f8"])
    result = material_observation(loose, "e1f1", best, played)
    assert (
        result["outcome"] == "ambiguous"
        and result["reason"] == "engine_disagreement_or_compensation"
    )


def test_protection_objective_witness_must_actually_remove_the_tested_threat():
    from chess_coach.material_observation import material_observation
    from chess_coach.material_witness import verified_witness

    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")
    best = {**line(["d4d5", "e8f8"]), "score_value": 500}
    played = line(["a2a3", "c5d4"])
    fact = material_observation(board, "a2a3", best, played)
    prepared = {"board": board, "context": {"played_move": "a2a3"}, "best": best, "played": played}
    assert fact["outcome"] == "failure"
    witness = verified_witness(prepared, fact)
    assert witness["role"] == "best" and witness["uci"][0] == "d4d5"


def test_preventable_loss_requires_a_concrete_verified_defense():
    from chess_coach.material_observation import material_observation

    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")
    best = {**line(["a2a3", "e8f8"]), "score_value": 500}
    played = line(["a2a3", "c5d4"])
    result = material_observation(board, "a2a3", best, played)
    assert result["outcome"] == "ambiguous" and result["reason"] == "alternative_defense_unverified"
