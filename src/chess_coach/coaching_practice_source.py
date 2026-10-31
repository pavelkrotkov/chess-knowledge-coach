"""Resolve an exact, current practice source for a coaching lesson."""

from .lesson_source import source
from .objective_capture_contract import TARGET_VERSION
from .objective_capture_current import current
from .objective_contract import VERSION as MATE_VERSION
from .unified_own_game import VERSION as MATERIAL_VERSION
from .unified_own_game_snapshot import key_for
from .unified_sources import resolve_source


def resolve_example(db, subject, lesson, example):
    evidence_id, position = example["evidence_id"], example["position_id"]
    inspected = source(db, subject, {"id": evidence_id, "position_id": position})
    if not inspected:
        return None
    evidence = inspected["evidence"]
    if (
        evidence["skill"],
        evidence["operation"],
        evidence["mapping_producer"],
        evidence["outcome"],
    ) != (lesson["skill"], lesson["operation"], lesson["family"], "failure"):
        return None
    if evidence["facts"][0]["detector_version"] != lesson["source_version"]:
        return None
    version, key, kind = _identity(db, subject, evidence)
    snapshot = resolve_source(db, "own-game", version, key, subject=subject)
    if (
        snapshot["prompt_fen"] != example["fen"]
        or snapshot["provenance"]["evidence_id"] != evidence_id
    ):
        return None
    return {
        "version": version,
        "key": key,
        "kind": kind,
        "evidence_id": evidence_id,
        "position_id": position,
    }


def _identity(db, subject, evidence):
    family, operation, skill = (
        evidence["mapping_producer"],
        evidence["operation"],
        evidence["skill"],
    )
    evidence_id = evidence["id"]
    if (family, skill, operation) == ("material-opportunity-mapper", "hanging_piece", "prevent"):
        view, _ = current(db, evidence_id, subject, kind="material_protection", operation="prevent")
        return MATERIAL_VERSION, key_for(view, evidence_id), "protection"
    supported = {
        ("bounded-mate-observation-mapper", "mate_in_one", "execute"): (MATE_VERSION, "mate"),
        ("material-opportunity-mapper", "hanging_piece", "execute"): (TARGET_VERSION, "capture"),
    }
    version, kind = supported.get((family, skill, operation), (None, None))
    if version is None:
        raise ValueError("practice unavailable")
    return version, str(evidence_id), kind
