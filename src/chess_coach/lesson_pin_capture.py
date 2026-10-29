"""Show tested captures after moving an already-pinned piece."""

from .lesson_adapter_common import line, valid_square


def exposure(evidence, note, fen):
    proof = note["proof"]
    trigger = (note.get("trigger") or {}).get("san")
    tested = line(fen, "Tested move and capture", [trigger, proof.get("san")])
    if not tested or not _valid_squares(proof):
        return [], []
    target = "the exposed piece" if proof["mode"] == "exposure" else "the pinned piece"
    origin = "recorded move" if trigger == evidence["lesson_played_san"] else "tested alternative"
    capture = proof["san"]
    consequence = _consequence(proof)
    if consequence is None:
        return [], []
    facts = [
        f"After the {origin} {trigger}, the tested response {capture} captures {target}.",
        consequence,
    ]
    return facts, _lines(note, fen, trigger, tested)


def _lines(note, fen, trigger, tested):
    alternative = note.get("alternative") or {}
    defense = line(fen, "Tested alternative defense", [alternative.get("san")])
    return [tested, defense] if defense and alternative.get("san") != trigger else [tested]


def _valid_squares(proof):
    return valid_square(proof.get("pinned")) and valid_square(proof.get("rear"))


def _consequence(proof):
    if proof.get("mate") is True:
        return "The tested capture checkmates immediately."
    if proof.get("minimum_gain") == 3:
        return "Every tested immediate reply leaves at least three pawn units of material gain."
    return None
