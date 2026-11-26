"""Present a current prepared-corpus capture preview."""

from .fact_fingerprint import canonical, digest
from .related_capture_familiar import familiarity
from .related_capture_pool import complete as prepared_window
from .related_capture_view import _assessment_options, present


def preview(db, subject, position, corpus_version, cursor=None, *, secret=None):
    from .related_capture import _selection

    before = db.connection.execute("PRAGMA data_version").fetchone()[0]
    familiar_data = familiarity(db, subject)
    selection = _selection(db, subject, position, corpus_version, familiar_data=familiar_data)
    result = present(selection, cursor, secret=secret)
    if selection is None:
        if cursor is not None:
            raise ValueError("capture preparation changed")
        ready = db.connection.execute(
            "SELECT 1 FROM puzzle_corpora WHERE version=? AND state='ready'",
            (corpus_version,),
        ).fetchone()
        if ready is not None:
            result["status"] = "capture preparation pending"
    # Only the browser receives opaque references and assessment controls.
    if secret is not None:
        _options(db, subject, corpus_version, cursor, selection, result, familiar_data[1])
    if db.connection.execute("PRAGMA data_version").fetchone()[0] != before:
        raise ValueError("capture selection changed")
    return result


def _options(db, subject, corpus_version, cursor, selection, result, games):
    if selection is None:
        return
    corpus = selection[2]
    window = prepared_window(
        db, db.capture_root, corpus_version, corpus["lower"], corpus["upper"], subject, games
    )
    if window is None or digest(canonical(window)) != corpus.get("capture_preparation"):
        raise ValueError("capture preparation changed")
    _assessment_options(
        db, result["items"], selection[3], cursor, result["scope"], subject, window=window
    )
