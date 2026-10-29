"""Read the detector inputs shared by full and provisional source checks."""

import json

from . import pawn_inspection
from .fact_fingerprint import canonical, digest


def recorded_inputs(db, fact):
    stored = db.connection.execute(
        "SELECT input_json FROM detector_runs WHERE id=?", (fact["detector_run_id"],)
    ).fetchone()
    inputs = json.loads(stored["input_json"])["detector_input"]
    return {key: value for key, value in inputs.items() if key != "reactivation"}


def preview_inputs(db, fact, fingerprint):
    inputs = recorded_inputs(db, fact)
    expected = {
        "source_fingerprint": fingerprint,
        "proof_manifest_sha256": pawn_inspection.MANIFEST_SHA256,
        "proof_version": pawn_inspection.VERSION,
        "proof_digest": digest(canonical(fact["payload"]["proof"])),
    }
    if inputs != expected:
        raise ValueError
    return inputs
