"""Atomically admit a capture transfer through unified sessions."""

from .related_capture_admission import admit
from .related_session_start import start_selected


def start_related(db, *, attempt_id, subject, position, corpus_version, reference):
    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key="related_capture",
        resolver=lambda: admit(db, subject, position, corpus_version, reference),
    )
