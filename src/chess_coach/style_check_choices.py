"""Compare root checks and bounded conditional king threats, not initiative."""


def _check_at(info, ply):
    return next((item for item in info["checks"] if item["ply"] == ply), None)


def _comparison(left, right, labels):
    if left == right:
        return None
    return labels[0] if left else labels[1]


def _check_choice(played, other, ply):
    left, right = _check_at(played, ply), _check_at(other, ply)
    if any(item and item["evasions"]["status"] != "complete" for item in (left, right)):
        return "ambiguous"
    return _comparison(bool(left), bool(right), ("check", "no_check"))


def _mate_choice(played, other):
    left, right = played["conditional_mate"], other["conditional_mate"]
    if left["status"] != "complete" or right["status"] != "complete":
        return "ambiguous"
    return _comparison(
        bool(left["moves"]),
        bool(right["moves"]),
        ("mate_available_after_reply", "no_mate_after_reply"),
    )


def classify(pair):
    names = ("root_check", "conditional_check", "conditional_mate")
    played, other = pair["played"], pair["alternative"]
    if "check_events" not in played or "check_events" not in other:
        return dict.fromkeys(names)
    left, right = played["check_events"], other["check_events"]
    if pair["root"]["in_check"]:
        return dict.fromkeys(names, "ambiguous")
    third = (
        "ambiguous"
        if left["pre_third_in_check"] or right["pre_third_in_check"]
        else _check_choice(left, right, 3)
    )
    return {
        "root_check": _check_choice(left, right, 1),
        "conditional_check": third,
        "conditional_mate": _mate_choice(left, right),
    }
