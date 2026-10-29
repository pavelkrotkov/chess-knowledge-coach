"""Contrast only independently supported responses to one named threat."""

NAMES = ("protect_move_target", "protect_capture_attacker")


def classify(pair):
    left = pair["played"].get("protection")
    right = pair["alternative"].get("protection")
    if left is None or right is None:
        return dict.fromkeys(NAMES)
    if left["status"] != "supported" or right["status"] != "supported":
        return dict.fromkeys(NAMES, "ambiguous")
    if left["target"] != right["target"] or left["evidence_id"] != right["evidence_id"]:
        return dict.fromkeys(NAMES, "ambiguous")
    return {
        "protect_move_target": _choice(left, right, "moved_target", "moved_target", "kept_target"),
        "protect_capture_attacker": _choice(
            left, right, "captured_attacker", "captured_attacker", "did_not_capture_attacker"
        ),
    }


def _choice(left, right, key, yes, no):
    if left[key] == right[key]:
        return None
    return yes if left[key] else no
