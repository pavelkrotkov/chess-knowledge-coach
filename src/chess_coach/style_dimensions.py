"""Classify contrasting endpoint proxies and conflicting alternatives."""

from .style_transitions import classify as transitions


def classify(pair):
    played, other = pair["played"], pair["alternative"]
    piece_delta = played["pieces"] - other["pieces"]
    material_delta = played["material"] - other["material"]
    attack_delta = played["enemy_half_attacks"] - other["enemy_half_attacks"]
    simplification = (
        "fewer_pieces" if piece_delta <= -2 else "more_pieces" if piece_delta >= 2 else None
    )
    tradeoff = None
    if abs(material_delta) >= 1 and abs(attack_delta) >= 3 and material_delta * attack_delta < 0:
        tradeoff = "more_material" if material_delta > 0 else "more_attacked_squares"
    return {"simplification": simplification, "material_activity": tradeoff, **transitions(pair)}


def dimensions(pairs):
    found = {
        name: set()
        for name in ("simplification", "material_activity", "queenless", "low_material_transition")
    }
    for pair in pairs:
        for name, value in classify(pair).items():
            if value:
                found[name].add(value)
    return {name: _vote(values) for name, values in found.items()}


def _vote(values):
    if "ambiguous" in values or len(values) > 1:
        return "ambiguous"
    return next(iter(values)) if values else None
