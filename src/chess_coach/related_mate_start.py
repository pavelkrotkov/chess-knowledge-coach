"""Atomically start a source-bound related mating example."""

from .related_mate import VERSION, selection
from .related_session_start import start_selected
from .related_transfer_admission import admit


def start_related(db, *, attempt_id, subject, evidence_id, corpus_version, reference):
    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key="related_mate",
        resolver=lambda: admit(
            selection(db, subject, evidence_id, corpus_version), reference, VERSION, "mate"
        ),
    )
