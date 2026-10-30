"""Existing material proof limits remain unknown, not negative claims."""

import chess
import pytest

from chess_coach.objective_protection_before import probe
from chess_coach.objective_protection_judge import judge


@pytest.mark.parametrize("flip", [False, True])
def test_recapturable_queen_is_not_a_proved_original_threat(flip):
    board = chess.Board()
    for move in ("e4", "d6", "d3", "Bg4"):
        board.push_san(move)
    if flip:
        board = board.mirror()
    assert probe(board) is None


@pytest.mark.parametrize("flip", [False, True])
def test_guard_and_checking_move_remain_unresolved(flip):
    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/6NK w - - 0 1")
    if flip:
        board = board.mirror()
    target = chess.D5 if flip else chess.D4
    guard = "g8f6" if flip else "g1f3"
    result = judge(board, board.parse_uci(guard), target, lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "unresolved"


def test_multiple_threats_and_harmless_positions_are_not_proved():
    from chess_coach.material_threats import threats

    multiple = chess.Board("4k3/8/8/2b5/1b1R4/N7/8/7K w - - 0 1")
    found = threats(multiple, hypothetical=True)
    assert found is not None and len(found["targets"]) == 2
    assert probe(multiple) is None
    assert probe(chess.Board()) is None


@pytest.mark.parametrize("flip", [False, True])
def test_checking_counterplay_is_not_promoted_to_supported_defense(flip):
    board = chess.Board("4k3/8/8/2b5/3R4/8/P7/7K w - - 0 1")
    if flip:
        board = board.mirror()
    target = chess.D5 if flip else chess.D4
    move = board.parse_uci("d5d1" if flip else "d4d8")
    assert board.gives_check(move)
    result = judge(board, move, target, lambda: 0.0, 0.0, 5.0, {})
    assert result["status"] == "unresolved"


@pytest.mark.parametrize("field", ["target", "evidence_id"])
def test_mixed_protection_sources_are_ambiguous(field):
    from chess_coach.style_protection_choices import classify

    left = {
        "status": "supported",
        "target": "c3",
        "evidence_id": 1,
        "moved_target": True,
        "captured_attacker": False,
    }
    right = {**left, "moved_target": False, "captured_attacker": True}
    right[field] = "d4" if field == "target" else 2
    result = classify({"played": {"protection": left}, "alternative": {"protection": right}})
    assert set(result.values()) == {"ambiguous"}


def test_missing_or_identical_responses_never_create_contrasts():
    from chess_coach.style_protection_choices import classify

    absent = classify({"played": {}, "alternative": {}})
    assert all(value is None for value in absent.values())
    source = {
        "status": "supported",
        "target": "c3",
        "evidence_id": 1,
        "moved_target": True,
        "captured_attacker": False,
    }
    same = classify(
        {"played": {"protection": source}, "alternative": {"protection": source.copy()}}
    )
    assert all(value is None for value in same.values())
