"""Retrieve source-bound first-ply fork execution transfers."""

from .related_capture import present
from .related_fork_features import fork_features
from .related_fork_match import candidate
from .related_fork_source import source_for_evidence
from .related_transfer_select import select

VERSION = "fork-execute-transfer-v1"


def selection(db, subject, evidence_id, corpus_version):
    source = source_for_evidence(db, subject, evidence_id)
    return select(
        db,
        subject,
        source,
        corpus_version,
        VERSION,
        theme="fork",
        all_lines=True,
        feature=fork_features,
        score=candidate,
    )


def preview(db, subject, evidence_id, corpus_version, cursor=None):
    chosen = selection(db, subject, evidence_id, corpus_version)
    result = present(chosen, cursor)
    if chosen is not None:
        result["source_outcome"] = chosen[0]["outcome"]
    return result
