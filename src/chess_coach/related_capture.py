"""Preview and safely select bounded capture-transfer practice."""

from .curriculum_capture_file_guard import current
from .fact_fingerprint import canonical, digest
from .related_capture_context import bounds as bounds
from .related_capture_cursor import PAGE as PAGE
from .related_capture_cursor import bind_scope
from .related_capture_familiar import familiarity
from .related_capture_features import certified_features
from .related_capture_pool import complete as prepared_window
from .related_capture_preview import preview as preview
from .related_capture_ready import score as prepared_score
from .related_capture_source import baseline, supported_source
from .related_capture_view import _assessment_options as _assessment_options
from .related_capture_view import _present as _present
from .related_capture_view import present as present
from .related_capture_view import unavailable
from .related_transfer_select import select

VERSION = "capture-transfer-v1"


def _selection(
    db,
    subject,
    position,
    corpus_version,
    *,
    familiar_data=None,
    rating_bounds=None,
    score=None,
    finder=False,
    difficulty=None,
):
    files = current(db, subject, db.capture_root)
    source = supported_source(db, subject, position)
    if score is not None or rating_bounds is not None:
        return None
    if familiar_data is None:
        familiar_data = familiarity(db, subject)
    games = familiar_data[1]
    from .capture_difficulty_binding import options

    lower, upper = options(difficulty).get("rating_bounds", bounds(baseline(db, source)))
    prepared = prepared_window(db, db.capture_root, corpus_version, lower, upper, subject, games)
    if prepared is None:
        return None
    selected = select(
        db,
        subject,
        source,
        corpus_version,
        VERSION,
        familiar_data=familiar_data,
        feature=certified_features,
        **options(difficulty, scorer=prepared_score(prepared)),
    )
    if (
        prepared_window(db, db.capture_root, corpus_version, lower, upper, subject, games)
        != prepared
    ):
        raise ValueError("capture preparation changed")
    fingerprint = digest(canonical(prepared))
    if selected is not None:
        selected[2]["capture_preparation"] = fingerprint
        selected[5]["qualification_unavailable"] = unavailable(prepared)
    return bind_scope(db, subject, selected, files, fingerprint, finder=finder)
