"""Select bounded source-bound immediate or short-mate execution examples."""

from .related_capture import present
from .related_mate_features import mate_features
from .related_mate_match import candidate
from .related_mate_source import source_for_evidence
from .related_transfer_select import select

VERSION = "mate-execution-transfer-v2"
FILTER_VERSION = "mate-execution-lines-v2"


def selection(db, subject, evidence_id, corpus_version):
    source = source_for_evidence(db, subject, evidence_id)
    theme = "mateIn1" if source["objective"] == "mate_in_one" else "mateIn2"
    return select(
        db,
        subject,
        source,
        corpus_version,
        VERSION,
        theme=theme,
        all_lines=True,
        include_objective=True,
        feature=mate_features,
        score=candidate,
    )


def preview(db, subject, evidence_id, corpus_version, cursor=None):
    chosen = selection(db, subject, evidence_id, corpus_version)
    result = present(chosen, cursor)
    if chosen is not None:
        result["source_outcome"] = chosen[0]["outcome"]
        result["mate_timing"] = chosen[0]["objective"]
    return result
