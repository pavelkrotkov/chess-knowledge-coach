"""Read the current first unassisted result for one exact owned fork."""

import json

from .fork_comparison_context import context
from .fork_followup_first import first
from .fork_followup_prior import _as_of
from .fork_history_item import item
from .fork_plan_history import _ambiguous, _candidates
from .related_fork import VERSION as RANK_VERSION


def read(db, subject, corpus, evidence, as_of, check):
    matches, boundary = _candidates(db, subject, evidence, check)
    if _ambiguous(matches[:2], boundary):
        return None
    row = matches[0]
    if row["source_version"] != corpus:
        return None
    first(db, subject, row)
    result = item(db, row, corpus, check)
    _as_of(row, result, as_of)
    if (result["status"], result.get("hints"), result.get("reveals")) not in {
        ("correct", 0, 0),
        ("incorrect", 0, 0),
    }:
        return None
    binding = json.loads(row["provenance_json"])["related_fork"]
    if (
        binding.get("evidence_id"),
        binding.get("motif"),
        binding.get("operation"),
        binding.get("pattern_cued"),
        binding.get("rank_version"),
    ) != (evidence, "fork", "execute", True, RANK_VERSION):
        return None
    assessment = binding["assessment"]
    if assessment.get("context") is None or assessment["context"] != context(
        db, corpus, row["source_key"]
    ):
        return None
    return {"row": row, "binding": binding, "result": result["status"]}
