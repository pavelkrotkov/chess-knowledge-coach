"""Atomically admit a source-bound capture rehearsal or assessment."""

from .curriculum_capture_file_guard import current
from .related_capture import VERSION, _selection, bounds
from .related_capture_prepared_assessment import attach
from .related_capture_view import _reference as _reference
from .related_session_start import start_selected
from .related_transfer_admission import admit
from .unified_source_current import require_current


def _admit(
    db,
    subject,
    position,
    corpus_version,
    reference,
    secret,
    assessment,
    *,
    finder=False,
    difficulty=None,
):
    if finder:
        from .related_capture_legacy import admit as finder_admit

        return finder_admit(
            db, subject, position, corpus_version, reference, secret, assessment, difficulty
        )
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
        attach(db, source_type, version, key, binding, selected, secret)
    return source_type, version, key, binding, lines


def start_related(
    db,
    *,
    attempt_id,
    subject,
    position,
    corpus_version,
    reference,
    assessment=False,
    secret=None,
    harder_attempt=None,
    finder=False,
):
    if db.connection.in_transaction:
        raise RuntimeError("cannot start during an existing transaction")
    difficulty = None
    if harder_attempt is not None:
        from .capture_difficulty import eligible

        if not assessment or secret is None:
            raise ValueError("harder capture assessment unavailable")
        difficulty = eligible(db, subject, corpus_version, position, harder_attempt)
        finder = True
    files = current(db, subject, db.capture_root)
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    from .related_capture_pool import observation
    from .related_capture_source import baseline, source_for_position

    prepared = None
    if not finder:
        source = source_for_position(db, subject, position)
        lower, upper = bounds(baseline(db, source))
        prepared = observation(db, db.capture_root, corpus_version, lower, upper)
    # Selection and certification stay outside the writer transaction.
    selected = (
        _admit(
            db,
            subject,
            position,
            corpus_version,
            reference,
            secret,
            True,
            finder=finder,
            difficulty=difficulty,
        )
        if assessment
        else None
    )

    def resolve():
        # Any intervening commit forces a fresh selection before admission.
        if selected is not None:
            if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
                raise ValueError("capture selection changed")
            return selected
        return _admit(
            db,
            subject,
            position,
            corpus_version,
            reference,
            secret,
            False,
            finder=finder,
            difficulty=difficulty,
        )

    def currentness(database, row):
        require_current(database, row)
        if files != current(database, subject, database.capture_root):
            raise ValueError("capture source changed")
        if not finder and prepared != observation(
            database, database.capture_root, corpus_version, lower, upper
        ):
            raise ValueError("capture preparation changed")

    return start_selected(
        db,
        attempt_id=attempt_id,
        subject=subject,
        corpus_version=corpus_version,
        reference=reference,
        binding_key="related_capture",
        currentness=currentness,
        resolver=resolve,
    )
