"""Validate a bounded objective witness without claiming a complete puzzle solution."""

from .material_observation import material_observation
from .material_witness_capture import capture_witness
from .material_witness_protection import protection_witness


def verified_witness(prepared, fact):
    fresh = material_observation(
        prepared["board"], prepared["context"]["played_move"], prepared["best"], prepared["played"]
    )
    if fresh != fact or fact.get("outcome") not in {"success", "failure"}:
        return None
    if fact["kind"] == "material_capture":
        return capture_witness(prepared["board"], fact)
    if fact["kind"] == "material_protection":
        return protection_witness(prepared, fact)
    return None
