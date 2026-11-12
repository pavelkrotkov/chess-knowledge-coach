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


def test_recorded_capture_and_missed_capture_are_bounded_observations(monkeypatch):
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

    # A legal opponent reply elsewhere can refute retained gain, even when an
    # earlier reply is unsupported. This is not a verdict on the played move.
    from chess_coach.capture_game_replies import inspect as inspect_replies
    from chess_coach.capture_game_roots import inspect as inspect_root

    counterexample = chess.Board("r3k3/8/8/8/3q4/8/7K/Q2R4 w - - 0 1")
    capture = chess.Move.from_uci("d1d4")
    after = counterexample.copy()
    after.push(capture)
    replies = list(after.legal_moves)
    refutation = chess.Move.from_uci("a8a1")
    assert refutation in replies and not after.gives_check(refutation)
    assert any(after.gives_check(reply) for reply in replies[: replies.index(refutation)])
    assert inspect_replies(counterexample, capture) == "disproved"
    assert inspect_root(counterexample, capture) == "outside"
    from chess_coach.capture_game_proof import classify

    only_capture = chess.Board("4k3/8/5n2/3Q4/7q/8/K7/7R w - - 0 1")
    assert classify(only_capture, "h1h4", 1, lambda: 0) == ("no_opportunity", None)
    ticks = iter([0, 0, 0, 2])
    assert classify(only_capture, "h1h4", 1, lambda: next(ticks, 2)) == ("unknown", "deadline")
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.capture_game_replies.MAX_REPLIES", 0)
        assert inspect_replies(counterexample, capture) == "unknown"
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.capture_game_replies._reply", lambda *_: "unknown")
        assert inspect_replies(counterexample, capture) == "unknown"
    assert counterexample.fen() == "r3k3/8/8/8/3q4/8/7K/Q2R4 w - - 0 1"
    # The game audit proves the same opportunity before inspecting either choice.
    from chess_coach.capture_game_proof import opportunities

    roots, unresolved, reason = opportunities(board, 1, lambda: 0)
    assert roots == {"d1d4"} and not unresolved and reason is None
    assert classify(board, "d1d4", 1, lambda: 0) == ("played", None)
    assert classify(board, "e1f1", 1, lambda: 0) == ("other", None)
    assert classify(chess.Board(), "e2e4", 1, lambda: 0) == ("no_opportunity", None)
    defended = chess.Board("4k3/8/8/2p5/3q4/8/8/3RK3 w - - 0 1")
    assert classify(defended, "e1f1", 1, lambda: 0) == ("no_opportunity", None)
    checking = chess.Board("3k4/8/8/8/3q4/8/8/3RK3 w - - 0 1")
    from chess_coach.material_check_proof import checking_capture

    proof = checking_capture(checking, capture)
    assert proof == {"minimum_gain": 9, "legal_replies": 4}
    roots, unresolved, reason = opportunities(checking, 1, lambda: 0)
    assert roots == {"d1d4"} and not unresolved and reason is None
    assert classify(checking, "d1d4", 1, lambda: 0) == ("played", None)
    assert classify(checking, "e1f1", 1, lambda: 0) == ("other", None)
    assert classify(checking.mirror(), "d8d5", 1, lambda: 0) == ("played", None)
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.material_check_proof.MAX_CHECK_REPLIES", 0)
        assert inspect_root(checking, capture) == "unknown"
    recaptured_check = chess.Board("3k4/8/8/2p5/3q4/8/8/3RK3 w - - 0 1")
    assert inspect_root(recaptured_check, capture) == "outside"
    assert classify(recaptured_check, "e1f1", 1, lambda: 0) == ("no_opportunity", None)
    uncertain_check = chess.Board("3k4/4N3/8/8/3q4/8/8/3RK3 w - - 0 1")
    assert inspect_root(uncertain_check, capture) == "unknown"
    assert classify(uncertain_check, "e1f1", 1, lambda: 0) == ("unknown", "unresolved_capture")
    unknown_history = chess.Board("4k3/8/8/8/3q4/8/8/3RK3 w - - 8 1")
    assert classify(unknown_history, "e1f1", 1, lambda: 0) == ("unknown", "unsupported_history")
    ticks = iter([0, 2])
    assert classify(chess.Board(), "e2e4", 1, lambda: next(ticks, 2)) == ("unknown", "deadline")
    with monkeypatch.context() as patch:
        patch.setattr("chess_coach.capture_game_proof.MAX_CANDIDATES", 0)
        assert classify(board, "e1f1", 1, lambda: 0) == ("unknown", "candidate_limit")
    with monkeypatch.context() as patch:
        patch.setattr(
            "chess_coach.capture_game_proof.opportunities",
            lambda *_: ({"d1d4"}, {"e1f1"}, None),
        )
        assert classify(board, "d1d4", 1, lambda: 0) == ("played", None)
        assert classify(board, "d1a1", 1, lambda: 0) == ("other", None)
        assert classify(board, "e1f1", 1, lambda: 0) == (
            "opportunity_unresolved",
            "played_capture_unresolved",
        )
    from chess_coach.capture_game_counts import add, empty, finish

    counts = empty(42)
    for number in range(20):
        add(
            counts,
            {"position_id": number, "played_move": "e1f1"},
            "unknown",
            "unresolved_capture",
            board,
        )
        add(
            counts,
            {"position_id": number, "played_move": "e1f1"},
            "opportunity_unresolved",
            "unresolved",
            board,
        )
    add(counts, {"position_id": 99, "played_move": "d1d4"}, "played", None, board)
    add(counts, {"position_id": 100, "played_move": "e1f1"}, "other", None, board)
    result = finish(counts)
    assert len(result["examples"]) == 20
    assert [row["position_id"] for row in result["examples"][:2]] == [99, 100]
    assert result["examples"][0]["played_san"] == "Rxd4"
    assert not result["complete"]
    monkeypatch.setattr("chess_coach.capture_game_roots.inspect_replies", lambda *_: "unknown")
    assert classify(board, "e1f1", 1, lambda: 0) == ("unknown", "unresolved_capture")
    assert board.fen() == "4k3/8/8/8/3q4/8/8/3RK3 w - - 0 1"


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
