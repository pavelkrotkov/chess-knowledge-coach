"""Admit an opaque source-bound protection transfer reference."""

from .related_protection import VERSION, selection
from .related_transfer_admission import admit as admit_selection


def admit(db, subject, evidence_id, corpus_version, reference):
    return admit_selection(
        selection(db, subject, evidence_id, corpus_version), reference, VERSION, "protection"
    )
