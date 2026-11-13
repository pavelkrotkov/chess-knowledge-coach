"""Atomically start a source-bound protection transfer."""

from .related_protection_admission import admit
from .related_session_start import start_selected


def start_related(
    db,
    *,
    attempt_id,
    subject,
    evidence_id,
    corpus_version,
    reference,
    assessment=False,
    followup=None,
    harder=False,
):
    if not all(
        isinstance(value, str) and 0 < len(value) <= 256
        for value in (attempt_id, subject, corpus_version, reference)
    ):
        raise ValueError("invalid transfer identity")
    if db.connection.in_transaction:
        raise RuntimeError("cannot start during an existing transaction")
    version = db.connection.execute("PRAGMA main.data_version").fetchone()[0]
    options = {"harder_attempt": followup} if harder else {}
    selected = admit(db, subject, evidence_id, corpus_version, reference, **options)
    from .protection_followup_mode import validate

    validate(db, subject, corpus_version, evidence_id, followup, assessment, selected, harder)
    if assessment:
        source_type, corpus, key, binding, lines = selected
        if source_type != "corpus":
            raise ValueError("protection assessment unavailable")
        from .related_protection_assessment import certificate

        binding["assessment"] = certificate(db, corpus, key, binding["objective_target"], lines)

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
