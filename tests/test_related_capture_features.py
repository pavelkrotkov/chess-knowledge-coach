"""Capture transfer features use the learner prompt and legal continuation."""

from chess_coach.related_capture_features import capture_features, corpus_features
from chess_coach.related_capture_position import compatible, similarity


def test_setup_is_replayed_before_classifying_and_illegal_lines_are_rejected():
    fen = "4k3/p7/8/3q4/8/2N5/P7/4K3 b - - 0 1"
    prompt, features = corpus_features(fen, "e8f8 c3d5")
    assert prompt.split()[1] == "w"
    assert features["geometry"] == (1, 2)
    assert capture_features(fen, ["c3d5"]) is None
    assert corpus_features(fen, "e8f8 c3d5 f8e7 a1a2") == (None, None)


def test_black_capture_matches_role_and_geometry_but_not_a_different_operation():
    white = capture_features("5k2/p7/8/3q4/8/2N5/P7/4K3 w - - 0 2", ["c3d5"])
    black = capture_features("4k3/p7/2n5/8/3Q4/8/P7/5K2 b - - 0 1", ["c6d4"])
    unrelated = capture_features("5k2/8/8/3q4/8/2R5/8/4K3 w - - 0 2", ["c3d3"])
    assert compatible(white, black)
    assert similarity(white, black)[0] == 1
    assert unrelated is None


def test_rank_uses_mechanism_excludes_duplicates_and_prefers_geometry():
    from chess_coach.related_capture_rank import rank

    source = {"prompt_fen": "5k2/p7/8/3q4/8/2N5/P7/4K3 w - - 0 2", "lines": ["c3d5"]}
    same = {
        "type": "public",
        "version": "v",
        "key": "same",
        "fen": source["prompt_fen"],
        "line": "c3d5",
    }
    better = {
        "type": "public",
        "version": "v",
        "key": "transfer",
        "fen": "5k2/p7/8/8/3q4/8/P1N5/4K3 w - - 0 2",
        "line": "c2d4",
    }
    unrelated = {
        "type": "public",
        "version": "v",
        "key": "unrelated",
        "fen": source["prompt_fen"],
        "line": "c3b5",
    }
    items = rank(source, [same, unrelated, better], set(), None)
    assert [item["key"] for item in items] == ["transfer"]
    assert "c2d4" not in str(items)
    assert not rank(source, [better], {items[0]["prompt_key"]}, None)
