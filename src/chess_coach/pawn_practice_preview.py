"""Check a provisional pawn source without treating recorded proof as verified."""

from .evidence_review_facts import facts_for_evidence
from .evidence_review_json import decode
from .evidence_review_state import _summary, evidence_row
from .learner_identity import normalize_identity
from .pawn_coach_contract import MAPPER
from .pawn_coach_current import _matches
from .pawn_coach_current_mapping import valid_mapping
from .pawn_coach_current_record import valid_record
from .pawn_coach_observation import observe
from .pawn_preview_source import recorded_source, resources_available


def preview(db, evidence_id, subject):
    try:
        row = evidence_row(db, evidence_id)
        evidence = _summary(row)
        evidence["context"] = decode(row["context_json"])
        evidence["facts"] = facts_for_evidence(db, evidence_id)
        if not _eligible(db, evidence, subject) or not resources_available():
            raise ValueError
        prepared = recorded_source(db, evidence)
        fact = evidence["facts"][0]
        if (
            prepared["fact"] != observe(prepared["fact"]["proof"], prepared["report"]["played_uci"])
            or not _matches(evidence, fact, prepared, prepared["inputs"])
            or not valid_mapping(db, evidence, fact, prepared)
        ):
            raise ValueError
        return {
            "key": str(evidence_id),
            "review_status": evidence["review_status"],
            "verification": "required",
        }
    except (ValueError, TypeError, KeyError, AttributeError, IndexError):
        raise ValueError("practice source unavailable") from None


def _eligible(db, evidence, subject):
    identity = normalize_identity(subject)
    return (
        identity is not None
        and evidence["subject"] == identity
        and evidence["mapping_producer"] == MAPPER
        and evidence["review_status"] in {"accepted", "unreviewed"}
        and evidence["outcome"] in {"success", "failure"}
        and valid_record(db, evidence)
    )
