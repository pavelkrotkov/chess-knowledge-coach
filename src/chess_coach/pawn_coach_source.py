"""Read an attributable decision and its versioned local pawn proof."""

from .fact_fingerprint import canonical, digest
from .material_context import context_for_position
from .pawn_coach_observation import observe
from .pawn_inspection import inspect_pawn


def prepare(db, position_id, learner):
    position = db.connection.execute(
        "SELECT * FROM positions WHERE id=?", (position_id,)
    ).fetchone()
    if position is None:
        raise ValueError("decision unavailable")
    context = context_for_position(db, position["game_id"], position_id, learner)
    report = inspect_pawn(db, position_id, learner=learner)
    if report["status"] != "current":
        raise ValueError("source unavailable")
    proof = report["proof"]
    inputs = {
        "source_fingerprint": report["source_fingerprint"],
        "proof_manifest_sha256": report["proof_manifest_sha256"],
        "proof_version": report["version"],
        "proof_digest": digest(canonical(proof)),
    }
    return {
        "position": position,
        "context": context,
        "report": report,
        "inputs": inputs,
        "fact": None if proof["status"] == "unsupported" else observe(proof, position["uci"]),
    }
