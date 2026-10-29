"""Validate that a protection witness removes the tested threat."""

from .material_defense import defense_observation


def protection_witness(prepared, fact):
    role = "played" if fact["outcome"] == "success" else "best"
    line = fact.get(role) or {}
    moves = line.get("uci") or []
    if not moves:
        return None
    source = prepared[role]
    trial = defense_observation(prepared["board"], moves[0], prepared["best"], source)
    if trial is None or trial.get("outcome") != "success":
        return None
    return {"role": role, "uci": moves, "san": line.get("san", [])}
