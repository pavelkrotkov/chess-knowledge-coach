"""Explain only the immediate mating difference between examined legal choices."""


def comparison(payload):
    played, alternative = payload["played"], payload.get("alternative")
    if not alternative:
        return ["No resolved legal alternative was found within the sampled moves."]
    mates = [item["san"] for item in played["checks"] if item["mate"]]
    other = [item["san"] for item in alternative["checks"] if item["mate"]]
    if not mates or other:
        return []
    threats = ", ".join(mates)
    move = alternative["move"]["san"]
    return [
        f"The played move permits immediate mate by {threats}; after the legal alternative {move}, no immediate opponent mate was found. This does not settle later safety or compensation."
    ]
