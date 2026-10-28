"""Verify linked completion versions, task identity and timestamps."""

from .mastery_training_request import matches_request, supported_mapper
from .mastery_training_terminal import terminal_lineage
from .training_feedback_item import puzzle_training_ref
from .training_feedback_rules import POLICY_VERSION


def valid_completion(row, evidence) -> bool:
    if row is None or row["policy_version"] != POLICY_VERSION:
        return False
    if not supported_mapper(row, evidence):
        return False
    return (
        _task_lineage(row, evidence)
        and terminal_lineage(row, evidence)
        and matches_request(row, evidence)
    )


def _task_lineage(row, evidence) -> bool:
    if row["source_type"] != "puzzle" or row["source_ref"] != puzzle_training_ref(
        row["corpus_version"], row["puzzle_id"]
    ):
        return False
    if (row["skill"], row["operation"]) != (evidence["skill"], evidence["operation"]):
        return False
    return (row["skill"], row["operation"]) == ("mate_in_one", "execute")
