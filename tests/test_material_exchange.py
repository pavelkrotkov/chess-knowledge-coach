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


def test_played_capture_succeeds_with_unavailable_best_line():
    from chess_coach.material_observation import material_observation

    board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    played = line(["d1d4", "e8f8"])
    result = material_observation(board, "d1d4", {"status": "unavailable"}, played)
    assert result["kind"] == "material_capture" and result["outcome"] == "success"
    assert result["best"] is None and result["played"]["san"][0] == "Rxd4"


def test_capture_of_attacker_can_protect_own_piece_without_best_line():
    from chess_coach.material_observation import material_observation

    board = chess.Board("4k3/8/8/2b5/1P1R4/8/8/7K w - - 0 1")
    played = line(["b4c5", "e8f8"])
    result = material_observation(board, "b4c5", {"status": "unavailable"}, played)
    assert result["kind"] == "material_protection" and result["outcome"] == "success"
    assert result["target"] == "d4" and result["best"] is None


def test_checking_capture_requires_all_legal_evasions_to_preserve_material():
    from chess_coach.material_observation import material_observation

    board = chess.Board("3k4/7p/8/8/3q4/8/P7/3R3K w - - 0 1")
    assert board.is_valid()
    played = line(["d1d4", "d8c7"])
    result = material_observation(board, "d1d4", {"status": "unavailable"}, played)
    assert result["outcome"] == "success"
    assert result["checking_reply_proof"]["legal_replies"] > 1
    assert result["checking_reply_proof"]["minimum_gain"] >= 3
    defended = chess.Board("3k4/7p/8/2b5/3q4/8/P7/3R3K w - - 0 1")
    assert defended.is_valid()
    result = material_observation(defended, "d1d4", {"status": "unavailable"}, played)
    assert result["outcome"] == "ambiguous"


def test_quiet_protection_succeeds_with_unavailable_best_line():
    from chess_coach.material_observation import material_observation

    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")
    played = line(["d4d5", "e8f8"])
    result = material_observation(board, "d4d5", {"status": "unavailable"}, played)
    assert result["kind"] == "material_protection" and result["outcome"] == "success"
    assert result["best"] is None


def test_unrelated_uncertain_target_does_not_veto_a_proven_target():
    from chess_coach.material_defense_rules import before_reason

    threatened = chess.D4
    other = chess.H4
    before = {"targets": {threatened: ["c5d4"]}, "uncertain": {other: ["g5h4"]}}
    assert before_reason(before) is None
    before["uncertain"][threatened] = ["e5d4"]
    assert before_reason(before) == "illegal_or_unresolved_attack"


def test_checking_capture_is_ambiguous_if_an_unplayed_evasion_recaptures():
    from chess_coach.material_check_proof import checking_capture
    from chess_coach.material_observation import material_observation

    board = chess.Board("3k4/7p/8/2b5/3q4/8/P7/3R3K w - - 0 1")
    move = chess.Move.from_uci("d1d4")
    after = board.copy()
    after.push(move)
    assert chess.Move.from_uci("c5d4") in after.legal_moves
    assert checking_capture(board, move) is None
    played = line(["d1d4", "d8c7"])
    result = material_observation(board, "d1d4", {"status": "unavailable"}, played)
    assert result["outcome"] == "ambiguous" and result["reason"] == "checking_capture_unresolved"


def test_unplayed_reply_capturing_different_material_prevents_decisive_claim():
    from chess_coach.material_observation import material_observation

    board = chess.Board("r3k3/8/8/8/3q4/8/Q7/3R3K w - - 0 1")
    assert board.is_valid()
    move = chess.Move.from_uci("d1d4")
    after = board.copy()
    after.push(move)
    assert chess.Move.from_uci("a8a2") in after.legal_moves
    played = line(["d1d4", "e8f8"])
    result = material_observation(board, "d1d4", {"status": "unavailable"}, played)
    assert result["outcome"] == "ambiguous"
    assert result["reason"] == "continuation_or_forcing_reply"


def test_protection_from_checking_material_threat_requires_all_evasions():
    from chess_coach.material_observation import material_observation
    from chess_coach.material_threats import threats

    board = chess.Board("3r4/p6k/5B2/3Q4/8/8/7P/3K4 w - - 0 1")
    assert board.is_valid()
    before = threats(board, hypothetical=True)
    assert before is not None and chess.D5 in before["targets"]
    played = line(["f6d8", "h7h6"])
    result = material_observation(board, "f6d8", {"status": "unavailable"}, played)
    assert result["kind"] == "material_protection" and result["outcome"] == "success"


def test_protection_that_exposes_new_material_remains_ambiguous():
    from chess_coach.material_observation import material_observation

    board = chess.Board("3r4/p6k/R4B2/3Q4/8/8/7P/3K4 w - - 0 1")
    assert board.is_valid()
    played = line(["a6d6", "a7a6"])
    result = material_observation(board, "a6d6", {"status": "unavailable"}, played)
    assert result["outcome"] == "ambiguous" and result["reason"] == "new_material_threat"


def test_immediate_reply_budget_exhaustion_fails_closed(monkeypatch):
    from chess_coach import material_reply_guard

    board = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    monkeypatch.setattr(material_reply_guard, "MAX_REPLIES", 0)
    assert material_reply_guard.unresolved_reply(board, chess.Move.from_uci("d1d4"))


def test_missed_capture_checking_reply_still_requires_resolved_line_and_score_veto():
    from chess_coach.material_observation import material_observation

    board = chess.Board("4k3/7p/8/8/3q4/8/P7/3RK3 w - - 0 1")
    best = {**line(["d1d4", "h7h6"]), "score_value": 600}
    played = {**line(["e1f1", "d4d1", "f1g2", "d1e2", "g2g1", "e8e7"]), "score_value": -600}
    result = material_observation(board, "e1f1", best, played)
    assert result["outcome"] == "failure" and result["exchange_gain"] == 9
    assert result["played"]["san"][1] == "Qxd1+"
    unresolved = {**played, "pv": "e1f1 d4d1"}
    assert (
        material_observation(board, "e1f1", best, unresolved)["reason"]
        == "continuation_unavailable"
    )
    equivalent = {**played, "score_value": 500}
    assert (
        material_observation(board, "e1f1", best, equivalent)["reason"]
        == "engine_disagreement_or_compensation"
    )
    bounded = {**played, "score_bound": "lower"}
    assert (
        material_observation(board, "e1f1", best, bounded)["reason"] == "continuation_unavailable"
    )


def test_checking_played_alternative_remains_ambiguous():
    from chess_coach.material_capture import capture_observation

    board = chess.Board("8/8/8/8/3q4/8/4k3/3R3K w - - 0 1")
    candidate = chess.Move.from_uci("d1d4")
    actual = chess.Move.from_uci("d1d2")
    assert board.is_valid() and actual in board.legal_moves and board.gives_check(actual)
    result = capture_observation(board, candidate, actual, line(["d1d4", "e2f2"]), {})
    assert (
        result["outcome"] == "ambiguous" and result["reason"] == "checking_alternative_unresolved"
    )


def test_missed_capture_keeps_four_ply_material_compensation_check():
    from chess_coach.material_observation import material_observation

    board = chess.Board("7k/8/8/3b2r1/8/8/8/KNB5 w - - 0 1")
    assert board.is_valid()
    best = {**line(["c1g5", "h8h7", "g5h4", "h7g8"]), "score_value": 1000}
    played = {**line(["b1c3", "h8g8", "c3d5", "g8h8"]), "score_value": 700}
    result = material_observation(board, "b1c3", best, played)
    assert result["outcome"] == "ambiguous"
    assert result["reason"] == "alternative_material_or_compensation"


def test_check_resolution_keeps_earlier_material_comparison_horizon():
    from chess_coach.material_lines import continuation

    board = chess.Board("4k3/8/8/3b2r1/8/8/8/KNB5 w - - 0 1")
    played = line(["b1c3", "e8e7", "c3d5", "e7e8"])
    assert board.is_valid()
    assert continuation(board, played, "b1c3") is None
    resolved = continuation(board, played, "b1c3", allow_checks=True, minimum_plies=4)
    assert resolved["material_delta"] == 3 and len(resolved["uci"]) == 4
    assert resolved["san"][2] == "Nxd5+"
    short = line(["b1c3", "e8e7"])
    assert continuation(board, short, "b1c3", allow_checks=True, minimum_plies=4) is None
