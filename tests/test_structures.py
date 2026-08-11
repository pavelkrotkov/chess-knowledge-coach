import chess

from chess_coach.structures import extract_features


def test_extracts_open_files_and_isolated_pawns() -> None:
    board = chess.Board("4k3/8/8/8/8/8/P7/4K3 w - - 0 1")

    features = extract_features(board)

    assert features["open_files"] == ["b", "c", "d", "e", "f", "g", "h"]
    assert features["half_open_files"]["white"] == []
    assert features["half_open_files"]["black"] == ["a"]
    assert features["isolated_pawns"]["white"] == ["a2"]


def test_detects_minority_deficit() -> None:
    board = chess.Board("4k3/8/8/8/ppp5/8/8/4K3 w - - 0 1")

    features = extract_features(board)

    assert features["minority_structure"]["white"] == ["queenside"]


def test_detects_locked_center_and_space() -> None:
    board = chess.Board("4k3/8/8/3pp3/3PP3/8/8/4K3 w - - 0 1")

    features = extract_features(board)

    assert features["locked_center"] is True
    assert features["space"]["white"] > 0
    assert features["space"]["black"] > 0
