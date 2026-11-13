"""Share one source and deadline across mate and material prevention."""

import time

from .discovery_mate_prevent_source import process_source as mate_source
from .material_source import prepare


def combined(db, position_id, learner, *, exclusions):
    from .discovery_material_pipeline import process_source as material_source

    if db.connection.in_transaction:
        raise RuntimeError("discovery defense detection requires an idle database")
    source = prepare(db, position_id, learner)
    started = time.monotonic()
    mate = mate_source(db, source, started=started)
    if mate["outcome"] == "failure":
        return mate
    material = material_source(db, source, started)
    if material and "material_unresolved" not in material:
        return {**material, "replayed": bool(mate["replayed"] and material["replayed"])}
    if material:
        exclusions[material["material_unresolved"]] += 1
    # Material was examined even when the unchanged mate result replayed.
    return {**mate, "replayed": False}
