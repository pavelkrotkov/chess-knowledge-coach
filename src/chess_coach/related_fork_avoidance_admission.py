"""Admit a source-bound opaque created-fork transfer reference."""

from .related_fork_avoidance import selection
from .related_fork_avoidance_contract import VERSION
from .related_transfer_admission import admit as admit_selection


def admit(db, subject, evidence_id, corpus_version, reference):
    return admit_selection(
        selection(db, subject, evidence_id, corpus_version), reference, VERSION, "fork_avoidance"
    )
