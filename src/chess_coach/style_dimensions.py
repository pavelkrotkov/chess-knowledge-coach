"""Classify contrasting endpoint proxies and conflicting alternatives."""


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
    return {"simplification": simplification, "material_activity": tradeoff}


def dimensions(pairs):
    found = {name: set() for name in ("simplification", "material_activity")}
    for pair in pairs:
        for name, value in classify(pair).items():
            if value:
                found[name].add(value)
    return {
        name: next(iter(values)) if len(values) == 1 else "ambiguous" if values else None
        for name, values in found.items()
    }
