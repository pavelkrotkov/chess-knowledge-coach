"""Contrast only independently supported responses to one named threat."""

from .style_protection_guard import classify as guard

LEGACY_NAMES = ("protect_move_target", "protect_capture_attacker")
NAMES = (*LEGACY_NAMES, "protect_guard")


def classify(pair):
    return {**_legacy(pair), "protect_guard": guard(pair)}


def _legacy(pair):
    left = pair["played"].get("protection")
    right = pair["alternative"].get("protection")
    if left is None or right is None:
        return dict.fromkeys(LEGACY_NAMES)
    if left["status"] != "supported" or right["status"] != "supported":
        return dict.fromkeys(LEGACY_NAMES, "ambiguous")
    if left["target"] != right["target"] or left["evidence_id"] != right["evidence_id"]:
        return dict.fromkeys(LEGACY_NAMES, "ambiguous")
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
