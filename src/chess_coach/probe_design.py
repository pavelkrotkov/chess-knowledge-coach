"""Construct small, proved tasks from the exact current lesson source."""

from .probe_fork import fork
from .probe_mate import mate
from .probe_pawn import pawn
from .probe_source import checked
from .unified_source_current import snapshot_hash


def design(db, subject, lesson_id, evidence_id, kind):
    lesson, example, fresh, evidence, decision = checked(db, subject, lesson_id, evidence_id)
    try:
        task = _task(kind, evidence, decision["decision_fen"])
    except (KeyError, TypeError, IndexError, AttributeError):
        raise ValueError("lesson proof unavailable") from None
    binding = {
        "lesson": lesson,
        "example": fresh,
        "facts": evidence["facts"],
        "fen": decision["decision_fen"],
    }
    return task, snapshot_hash(binding), example["position_id"]


def _task(kind, evidence, fen):
    if kind == "recognize" and evidence["mapping_producer"] == "fork-opportunity-mapper":
        return fork(evidence, fen)
    if kind == "recognize" and evidence["mapping_producer"] == "bounded-mate-observation-mapper":
        return mate(evidence, fen)
    if kind == "evaluate" and evidence["mapping_producer"] == "pawn-endgame-mapper":
        return pawn(evidence, fen)
    raise ValueError("no supported probe for this source")
