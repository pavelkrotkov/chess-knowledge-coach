"""Validate a bounded objective witness without claiming a complete puzzle solution."""

from .material_observation import material_observation
from .material_witness_capture import capture_witness
from .material_witness_protection import protection_witness


def verified_witness(prepared, fact, *, check=None):
    options = {"check": check} if check is not None else {}
    fresh = material_observation(
        prepared["board"],
        prepared["context"]["played_move"],
        prepared["best"],
        prepared["played"],
        **options,
    )
    if fresh != fact or fact.get("outcome") not in {"success", "failure"}:
        return None
    if fact["kind"] == "material_capture":
        return capture_witness(prepared["board"], fact)
    if fact["kind"] == "material_protection":
        return protection_witness(prepared, fact, **options)
    return None
