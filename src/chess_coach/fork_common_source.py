"""Bind an exact owned fork and its first unassisted result."""

from .curriculum_fork_source import read as source_read
from .fork_common_control import current
from .fork_context_source import _match
from .fork_first_result import read as first_result
from .objective_fork_contract import MISS_VERSION
from .objective_fork_source import resolve


def bind(db, subject, corpus, as_of, report, check):
    candidate, _, source = source_read(db, subject, corpus, check)
    if candidate is None or source["limited"]:
        return None
    evidence = candidate["source_evidence_id"]
    practice = first_result(db, subject, corpus, evidence, as_of, check)
    if practice is None:
        return None
    snapshot = resolve(db, MISS_VERSION, str(evidence), subject, check=check)
    turns = report["newer"]["root_details"] + report["earlier"]["root_details"]
    matched = _match(snapshot, turns)
    if matched is None:
        return None
    source_turn, root = matched
    row, binding = practice["row"], practice["binding"]
    if row["learner_color"] != source_turn["side"]:
        return None
    controls = current(db, row, binding, source_turn["side"])
    if controls is None:
        return None
    return {"turn": source_turn, "root": root, "practice": practice, "controls": controls}
