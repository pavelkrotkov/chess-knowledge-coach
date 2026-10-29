"""Contrast explicit conditional central-pawn facts for one alternative."""


def _difference(played, other, labels):
    left, right = set(played) - set(other), set(other) - set(played)
    if left and right:
        return "ambiguous"
    if left:
        return labels[0]
    if right:
        return labels[1]
    return None


def _event_choice(played, other, kind, labels):
    left = bool(played["center_events"][kind])
    right = bool(other["center_events"][kind])
    return labels[0] if left and not right else labels[1] if right and not left else None


def _lock(root, played, other):
    before = root["center_locked"]
    left, right = played["center_locked"], other["center_locked"]
    if left == right:
        return None
    if before:
        return "skeleton_retained" if left else "skeleton_left"
    return "skeleton_entered" if left else "skeleton_absent"


def classify(pair):
    root, played, other = pair.get("root", {}), pair["played"], pair["alternative"]
    names = (
        "center_contact",
        "center_pawn_capture",
        "center_pawn_exchange",
        "center_file_opening",
        "center_lock",
    )
    if "center_events" not in played or "center_events" not in other:
        return dict.fromkeys(names)
    previously_open = set(root["center_open_files"])
    return {
        "center_contact": _difference(
            played["center_contacts"],
            other["center_contacts"],
            ("contact_present", "contact_absent"),
        ),
        "center_pawn_capture": _event_choice(played, other, "captures", ("capture", "no_capture")),
        "center_pawn_exchange": _event_choice(
            played, other, "exchanges", ("exchange", "no_exchange")
        ),
        "center_file_opening": _difference(
            set(played["center_open_files"]) - previously_open,
            set(other["center_open_files"]) - previously_open,
            ("file_opened", "file_still_occupied"),
        ),
        "center_lock": _lock(root, played, other),
    }
