"""Bound other-move rates without assigning outcomes to unresolved turns."""


def _sufficient(sample):
    return sample["played"] + sample["other"] >= 5 and sample["resolved_games"] >= 3


def _range(sample):
    other, played = sample["other"], sample["played"]
    unresolved = sample["unknown"] + sample["opportunity_unresolved"]
    return {
        "lower": other,
        "upper": other + unresolved,
        "total": other + played + unresolved,
        "unresolved": unresolved,
    }


def _direction(earlier, newer):
    if newer["upper"] * earlier["total"] < earlier["lower"] * newer["total"]:
        return "lower"
    if earlier["upper"] * newer["total"] < newer["lower"] * earlier["total"]:
        return "higher"
    return "overlap"


def bounds(comparable, earlier, newer):
    if not comparable:
        return {"status": "incomparable"}
    if earlier["unchecked"] or newer["unchecked"]:
        return {"status": "pending"}
    if not all(_sufficient(sample) for sample in (earlier, newer)):
        return {"status": "sparse"}
    old, new = _range(earlier), _range(newer)
    return {"status": "available", "earlier": old, "newer": new, "direction": _direction(old, new)}
