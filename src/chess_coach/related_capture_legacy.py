"""Preserve the explicit verified-finder path until prepared finder delivery."""

from .capture_difficulty_binding import difficulty_scope, options, progression
from .fact_fingerprint import canonical, digest
from .related_capture_cursor import bind_scope
from .related_capture_features import certified_features
from .related_capture_prepared_assessment import legacy_assessment
from .related_capture_view import _reference
from .related_transfer_admission import admit as admit_selection
from .related_transfer_select import select


def choose(db, subject, position, corpus, familiar_data, difficulty):
    from .curriculum_capture_file_guard import current
    from .related_capture import VERSION, _selection
    from .related_capture_source import supported_source

    if difficulty is None:
        from .capture_finder_prepared import PreparationPending

        selected = _selection(
            db, subject, position, corpus, familiar_data=familiar_data, finder=True
        )
        if selected is None:
            raise PreparationPending()
        return selected
    files = current(db, subject, db.capture_root)
    source = supported_source(db, subject, position)
    selected = select(
        db,
        subject,
        source,
        corpus,
        VERSION,
        familiar_data=familiar_data,
        feature=certified_features,
        **options(difficulty),
    )
    selected = bind_scope(db, subject, selected, files)
    if selected is None:
        return None
    scope = digest(canonical(["verified-capture-finder-v1", selected[4]]))
    return (*selected[:4], scope, selected[5])


def admit(db, subject, position, corpus, reference, secret, assessment_requested, difficulty):
    from .related_capture import VERSION

    if secret is None:
        raise ValueError("capture finder unavailable")
    selected = choose(db, subject, position, corpus, None, difficulty)
    if selected is None:
        raise ValueError("capture selection unavailable")
    selected = difficulty_scope(selected, difficulty)
    reference = _reference(selected, reference, secret)
    source_type, version, key, binding, lines = admit_selection(
        selected, reference, VERSION, "material_capture"
    )
    if assessment_requested:
        if source_type != "corpus":
            raise ValueError("capture assessment unavailable")
        binding["assessment"] = legacy_assessment(db, version, key, selected)
    progression(binding, version, difficulty)
    return source_type, version, key, binding, lines
