"""Conditional endpoint contrasts, never claims about observed games or intent."""


def _contrast(played, other, low, high, labels):
    if played == low and other == high:
        return labels[0]
    if played == high and other == low:
        return labels[1]
    return None


def _queen_state(item):
    if item.get("queens") == 0:
        return "queenless"
    if item.get("one_queen_each"):
        return "both_queens"
    return "ambiguous"


def classify(pair):
    root = pair.get("root", {})
    played, other = pair["played"], pair["alternative"]
    queen = None
    if root.get("one_queen_each"):
        values = (_queen_state(played), _queen_state(other))
        if "ambiguous" in values:
            queen = "ambiguous"
        else:
            queen = _contrast(*values, "queenless", "both_queens", ("queenless", "both_queens"))
    phase = None
    if root.get("pieces", 0) >= 6:
        phase = _contrast(
            played["pieces"] < 6,
            other["pieces"] < 6,
            True,
            False,
            ("fewer_than_six_pieces", "six_or_more_pieces"),
        )
    return {"queenless": queen, "low_material_transition": phase}
