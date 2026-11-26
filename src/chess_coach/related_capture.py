"""Preview and safely select bounded capture-transfer practice."""

from .curriculum_capture_file_guard import current
from .fact_fingerprint import canonical, digest
from .related_capture_context import bounds as bounds
from .related_capture_cursor import PAGE as PAGE
from .related_capture_cursor import bind_scope
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
):
    files = current(db, subject, db.capture_root)
    source = supported_source(db, subject, position)
    if finder:
        from .related_capture_legacy import selection as finder_selection

        return finder_selection(
            db, subject, source, corpus_version, VERSION, files, familiar_data, rating_bounds, score
        )
    if score is not None or rating_bounds is not None:
        return None
    options = {"feature": certified_features}
    lower, upper = bounds(baseline(db, source))
    prepared = prepared_window(db, db.capture_root, corpus_version, lower, upper)
    if prepared is None:
        return None
    public_pending = [False]
    options["score"] = prepared_score(prepared, public_pending)
    selected = select(
        db, subject, source, corpus_version, VERSION, familiar_data=familiar_data, **options
    )
    if public_pending[0]:
        return None
    if prepared_window(db, db.capture_root, corpus_version, lower, upper) != prepared:
        raise ValueError("capture preparation changed")
    fingerprint = digest(canonical(prepared))
    if selected is not None:
        selected[2]["capture_preparation"] = fingerprint
        selected[5]["qualification_unavailable"] = unavailable(prepared)
    return bind_scope(db, subject, selected, files, fingerprint)
