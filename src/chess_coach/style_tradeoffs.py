"""Existing material and piece-count endpoint tradeoffs."""


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
