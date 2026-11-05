"""Atomically admit a source-bound capture rehearsal or assessment."""

from .fact_fingerprint import canonical, digest
from .related_capture import VERSION, _selection
from .related_mate_search_token import fingerprint
from .related_session_start import start_selected
from .related_transfer_admission import admit


def _reference(selected, reference, secret):
    scope = selected[4]
    for item in selected[3]:
        identity = [scope, item["type"], item["version"], item["key"]]
        if fingerprint(secret, "capture-reference", identity) == reference:
            return digest(canonical(identity))
    raise ValueError("capture selection changed")


def _admit(db, subject, position, corpus_version, reference, secret, assessment):
    if secret is None and not assessment:
        from .related_capture_admission import admit as legacy_admit

        return legacy_admit(db, subject, position, corpus_version, reference)
    selected = _selection(db, subject, position, corpus_version)
    if selected is None:
        raise ValueError("capture selection unavailable")
    if secret is not None:
        reference = _reference(selected, reference, secret)
    source_type, version, key, binding, lines = admit(
        selected, reference, VERSION, "material_capture"
    )
    if assessment:
        if secret is None or source_type != "corpus":
            raise ValueError("capture assessment unavailable")
        from .related_capture_assessment import certificate

        binding["assessment"] = certificate(db, version, key)
    return source_type, version, key, binding, lines


def start_related(
    db, *, attempt_id, subject, position, corpus_version, reference, assessment=False, secret=None
):
    if db.connection.in_transaction:
        raise RuntimeError("cannot start during an existing transaction")
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    # Selection and certification stay outside the writer transaction.
    selected = (
        _admit(db, subject, position, corpus_version, reference, secret, True)
        if assessment
        else None
    )

    def resolve():
        # Any intervening commit forces a fresh selection before admission.
        if selected is not None:
            if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
                raise ValueError("capture selection changed")
            return selected
        return _admit(db, subject, position, corpus_version, reference, secret, False)

    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key="related_capture",
        resolver=resolve,
    )
