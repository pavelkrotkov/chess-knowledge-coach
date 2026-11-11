"""Atomically start a source-bound protection transfer."""

from .related_protection_admission import admit
from .related_session_start import start_selected


def start_related(db, *, attempt_id, subject, evidence_id, corpus_version, reference):
    if not all(
        isinstance(value, str) and 0 < len(value) <= 256
        for value in (attempt_id, subject, corpus_version, reference)
    ):
        raise ValueError("invalid transfer identity")
    if db.connection.in_transaction:
        raise RuntimeError("cannot start during an existing transaction")
    version = db.connection.execute("PRAGMA main.data_version").fetchone()[0]
    selected = admit(db, subject, evidence_id, corpus_version, reference)

    def current_selection():
        if db.connection.execute("PRAGMA main.data_version").fetchone()[0] != version:
            raise ValueError("transfer selection changed; preview again")
        return selected

    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key="related_protection",
        resolver=current_selection,
    )
