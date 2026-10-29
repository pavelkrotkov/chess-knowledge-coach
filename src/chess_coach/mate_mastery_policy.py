"""Fail closed for game-derived mate skills except the exact legacy policy."""

from .evidence_review_facts import facts_for_evidence
from .mate_legacy_mastery import legacy_fact, matches_game


def mastery_allowed(db, row):
    if row["skill"] not in {"mate_in_one", "calculation"}:
        return True
    if not _legacy_mapping(row):
        return False
    facts = facts_for_evidence(db, row["id"])
    return (
        len(facts) == 1
        and legacy_fact(facts[0], row["outcome"])
        and matches_game(db, row, facts[0])
    )


def _legacy_mapping(row):
    return (
        row["skill"] == "mate_in_one"
        and row["operation"] == "execute"
        and row["mapping_producer"] == "mate-in-one-mapper"
        and row["mapper_version"] == row["run_mapper_version"] == "mate-one-1.0.0"
        and row["link_count"] == 1
    )
