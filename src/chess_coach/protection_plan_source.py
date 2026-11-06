"""Resolve an exact recurrence marker as a current prepared protection replay."""

import chess

from .objective_capture_current import current
from .unified_own_game import VERSION
from .unified_own_game_snapshot import key_for
from .unified_sources import resolve_source


def resolve(db, subject, item):
    evidence_id = item["id"]
    view, _ = current(db, evidence_id, subject, kind="material_protection", operation="prevent")
    if view["outcome"] != "failure" or view["lineage"]["detector_version"] != item["version"]:
        raise ValueError("protection source differs")
    key = key_for(view, evidence_id)
    snapshot = resolve_source(db, "own-game", VERSION, key, subject=subject)
    provenance = snapshot["provenance"]
    if (
        provenance["evidence_id"] != evidence_id
        or provenance["position_id"] != item["position_id"]
        or snapshot["prompt_fen"] != chess.Board(item["decision"]["pre_move_fen"]).fen()
    ):
        raise ValueError("protection source differs")
    return {
        "version": VERSION,
        "key": key,
        "evidence_id": evidence_id,
        "color": snapshot["learner_color"],
        "review_status": provenance["review_status"],
    }
