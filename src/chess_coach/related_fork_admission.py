"""Resolve opaque references to one current fork-execution source."""

from .related_fork import VERSION, selection
from .related_transfer_admission import admit as admit_selection


def admit(db, subject, evidence_id, corpus_version, reference):
    chosen = selection(db, subject, evidence_id, corpus_version)
    return admit_selection(chosen, reference, VERSION, "fork")
