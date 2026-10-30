"""Atomically admit a selected back-rank attack transfer."""

from . import related_backrank_contract as contract
from .related_backrank_attack import selection
from .related_session_start import start_selected
from .related_transfer_admission import admit


def start_related(db, *, attempt_id, subject, evidence_id, corpus_version, root_move, reference):
    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key="related_backrank_attack",
        resolver=lambda: admit(
            selection(db, subject, evidence_id, corpus_version, root_move),
            reference,
            contract.VERSION,
            "backrank_attack",
        ),
    )
