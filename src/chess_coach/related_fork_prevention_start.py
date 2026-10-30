"""Atomically start source-bound anchored fork-prevention practice."""

from .related_fork_prevention_admission import admit
from .related_session_start import start_selected


def start_related(db, *, attempt_id, subject, evidence_id, corpus_version, reference):
    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key="related_fork_prevention",
        resolver=lambda: admit(db, subject, evidence_id, corpus_version, reference),
    )
