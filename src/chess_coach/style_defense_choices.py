"""Contrast overlapping legal responses only in an actual check context."""

from .style_defense_evasion import response

NAMES = ("defense_king", "defense_capture", "defense_interpose", "defense_countercheck")


def annotate(board, compared):
    played = response(board, compared["played"]["root_move"])
    for pair in compared["pairs"]:
        pair["played"]["defense_response"] = played
        pair["alternative"]["defense_response"] = response(
            board, pair["alternative_line"]["root_move"]
        )


def classify(pair):
    left = pair["played"].get("defense_response")
    right = pair["alternative"].get("defense_response")
    if left is None or right is None:
        return dict.fromkeys(NAMES)
    return {
        "defense_king": _choice(left, right, "king_move", "king_move", "non_king_move"),
        "defense_capture": _choice(left, right, "capture", "capture", "non_capture"),
        "defense_interpose": _choice(
            left, right, "interposition", "interposition", "other_evasion"
        ),
        "defense_countercheck": _choice(
            left, right, "countercheck", "countercheck", "no_countercheck"
        ),
    }


def _choice(left, right, key, yes, no):
    if left[key] == right[key]:
        return None
    return yes if left[key] else no
