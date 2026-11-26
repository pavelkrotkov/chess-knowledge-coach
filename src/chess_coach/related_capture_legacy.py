"""Preserve the explicit verified-finder path until prepared finder delivery."""

from .capture_difficulty_binding import difficulty_scope, progression
from .related_capture_prepared_assessment import legacy_assessment
from .related_capture_view import _reference
from .related_transfer_admission import admit as admit_selection


def choose(db, subject, position, corpus, familiar_data, difficulty):
    from .capture_finder_prepared import PreparationPending
    from .related_capture import _selection

    selected = _selection(
        db,
        subject,
        position,
        corpus,
        familiar_data=familiar_data,
        finder=True,
        difficulty=difficulty,
    )
    if selected is None:
        raise PreparationPending()
    return selected


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
