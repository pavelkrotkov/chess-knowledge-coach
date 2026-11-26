"""Atomically admit a source-bound capture rehearsal or assessment."""

from .capture_difficulty_binding import difficulty_scope, options, progression
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
    familiar_data=None,
):
    if familiar_data is None:
        from .related_capture_familiar import familiarity

        familiar_data = familiarity(db, subject)
    selected = _selection(
        db,
        subject,
        position,
        corpus_version,
        familiar_data=familiar_data,
        finder=finder,
        difficulty=difficulty,
    )
    if selected is None:
        raise ValueError("capture selection unavailable")
    selected = difficulty_scope(selected, difficulty)
    reference = _reference(selected, reference, secret, finder=finder)
    source_type, version, key, binding, lines = admit(
        selected, reference, VERSION, "material_capture"
    )
    if assessment:
        attach(db, source_type, version, key, binding, selected, secret, subject, familiar_data[1])
    progression(binding, version, difficulty)
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
        from .capture_difficulty import eligible, operation_check

        if not assessment or secret is None:
            raise ValueError("harder capture assessment unavailable")
        check = operation_check(db)
        difficulty = eligible(db, subject, corpus_version, position, harder_attempt, check)
        finder = True
    files = current(db, subject, db.capture_root)
    version = db.connection.execute("PRAGMA data_version").fetchone()[0]
    from .related_capture_familiar import familiarity
    from .related_capture_pool import observation
    from .related_capture_source import baseline, source_for_position

    familiar_data = familiarity(db, subject)
    games = familiar_data[1]
    source = source_for_position(db, subject, position)
    lower, upper = options(difficulty).get("rating_bounds", bounds(baseline(db, source)))
    prepared = observation(db, db.capture_root, corpus_version, lower, upper, subject, games)
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
            familiar_data=familiar_data,
        )
        if assessment
        else None
    )

    def resolve():
        if difficulty is not None:
            check()
        # Any intervening commit forces a fresh selection before admission.
        if db.connection.execute("PRAGMA data_version").fetchone()[0] != version:
            raise ValueError("capture selection changed")
        if selected is not None:
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
            familiar_data=familiar_data,
        )

    def currentness(database, row):
        if difficulty is not None:
            check()
        require_current(database, row)
        if files != current(database, subject, database.capture_root):
            raise ValueError("capture source changed")
        if prepared != observation(
            database,
            database.capture_root,
            corpus_version,
            lower,
            upper,
            subject,
            games,
        ):
            raise ValueError("capture preparation changed")
        if difficulty is not None:
            check()

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
