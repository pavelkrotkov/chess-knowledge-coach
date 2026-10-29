"""Check current source and witness before marking an opportunity eligible."""

from .material_source import prepare
from .material_source_marker import source_marker
from .material_witness import verified_witness


def verify_current(db, learner, evidence, fact, source, result):
    if evidence["lifecycle_status"] != "active" or fact["detector_status"] != "active":
        return
    try:
        prepared = prepare(db, evidence["position_id"], learner)
        if not _same_source(prepared, source):
            return
        witness = verified_witness(prepared, fact["payload"])
        if (
            source_marker(db, evidence["position_id"], evidence["game_id"], learner)
            != prepared["source_marker"]
        ):
            return
    except (ValueError, TypeError, KeyError):
        return
    result["currentness"] = "current"
    result["learner_color"] = prepared["context"]["learner_color"]
    result["objective_witness"] = witness
    result["eligible_for_exercise_candidate"] = bool(
        witness
        and result["family_validated"]
        and evidence["review_status"] not in {"rejected", "revoked"}
    )


def _same_source(prepared, source):
    return prepared["source_marker"] == source.get("source_marker") and prepared[
        "provenance"
    ] == source.get("provenance")
