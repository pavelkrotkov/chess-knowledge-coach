"""Admit a certified unfamiliar fork without proving under a writer lock."""

from .recurrence_cursor import _valid_id
from .related_capture_start import _reference
from .related_fork import VERSION, selection
from .related_fork_assessment import certificate
from .related_fork_current import check_admitted
from .related_session_start import start_selected
from .related_transfer_admission import admit


def start(db, *, attempt_id, subject, evidence_id, corpus_version, reference, secret, prior=None):
    if not _valid_id(evidence_id):
        raise ValueError("fork assessment unavailable")
    if db.connection.in_transaction:
        raise RuntimeError("cannot start during an existing transaction")
    data_version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    selected = selection(db, subject, evidence_id, corpus_version)
    if selected is None or selected[0]["outcome"] != "failure" or secret is None:
        raise ValueError("fork assessment unavailable")
    from .fork_followup_admission import attach
    from .fork_followup_admission import reference as matched_reference

    selected_reference, expected = (
        (_reference(selected, reference, secret), None)
        if prior is None
        else matched_reference(db, selected, subject, corpus_version, secret, reference, prior)
    )
    resolved = admit(selected, selected_reference, VERSION, "fork")
    source_type, version, key, binding, _ = resolved
    if source_type != "corpus":
        raise ValueError("fork assessment unavailable")
    binding["assessment"] = certificate(db, version, key)
    attach(db, resolved, expected)

    def resolve():
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != data_version:
            raise ValueError("fork assessment changed")
        return resolved

    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        resolver=resolve,
        binding_key="related_fork",
        currentness=check_admitted,
    )
