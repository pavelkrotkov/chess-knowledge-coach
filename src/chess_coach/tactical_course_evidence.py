"""Bind current supporting examples to independent verified game identities."""

from .course_evidence import revalidate_group
from .fact_fingerprint import canonical, digest
from .lesson_source import source
from .mastery_game_lookup import decisions_for_game


def _binding(db, subject, example):
    current = source(
        db, subject, {"id": example["evidence_id"], "position_id": example["position_id"]}
    )
    decisions = decisions_for_game(db, example["game_id"], subject)
    decision = decisions.get(example["position_id"]) if decisions else None
    if not current or not decision or not decision["subject"]:
        raise ValueError("lesson decision unavailable")
    evidence = current["evidence"]
    reviews = evidence["reviews"]
    return {
        "game_key": decision["game_key"],
        "evidence_id": evidence["id"],
        "position_id": evidence["position_id"],
        "mapping_run_id": evidence["mapping_run_id"],
        "fact_ids": [fact["id"] for fact in evidence["facts"]],
        "review_event_id": reviews[-1]["id"] if reviews else None,
        "lineage_sha256": digest(canonical(current)),
    }


def independent(db, subject, group):
    revalidate_group(db, subject, group)
    bindings = [_binding(db, subject, example) for example in group["lesson"]["examples"]]
    if len({item["game_key"] for item in bindings}) < 2:
        raise ValueError("independent lesson games unavailable")
    return bindings
