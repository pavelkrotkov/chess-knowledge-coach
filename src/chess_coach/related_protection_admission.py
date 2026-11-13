"""Admit an opaque source-bound protection transfer reference."""

from .related_protection import VERSION, selection
from .related_transfer_admission import admit as admit_selection


def admit(
    db, subject, evidence_id, corpus_version, reference, *, harder_attempt=None, difficulty=None
):
    options = {"difficulty": difficulty} if difficulty is not None else {}
    chosen = selection(db, subject, evidence_id, corpus_version, **options)
    if harder_attempt and chosen is not None:
        from .protection_difficulty import scope

        chosen = (*chosen[:4], scope(chosen[4], evidence_id, harder_attempt), chosen[5])
    return admit_selection(chosen, reference, VERSION, "protection")
