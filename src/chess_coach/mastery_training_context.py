"""Resolve verified puzzle prompts from immutable completion lineage."""

from .db import Database
from .mastery_training_lineage import valid_completion
from .mastery_training_source import completion_source
from .mastery_training_validation import verified_prompt


def training_context(db: Database, evidence):
    row = completion_source(db, evidence["id"])
    if row is None and not db.compat32:
        from .mastery_unified_training import training_context as unified_context

        return unified_context(db, evidence)
    try:
        valid = valid_completion(row, evidence)
    except (ValueError, TypeError, AttributeError):
        valid = False
    if not valid:
        return None, "invalid_training_lineage"
    try:
        prompt = verified_prompt(row, evidence["outcome"])
    except (ValueError, TypeError, IndexError, AttributeError):
        return None, "invalid_training_snapshot"
    return {"kind": "training", "attempt_id": row["attempt_id"], "prompt_fen": prompt}, None
