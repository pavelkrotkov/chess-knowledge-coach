"""Build one source-bound, prepared named-capture practice chapter."""

from .related_capture import _selection
from .related_capture_pool import complete
from .related_capture_prepared_assessment import assessment
from .related_capture_ready import entries
from .tactical_course_capture_chapter import chapter
from .tactical_course_related import GENERAL_EMPTY
from .tactical_course_thematic_exposure import exposure


def practice(db, subject, corpus, choice, familiar_data, *, artifact=None):
    selected = _selection(db, subject, choice["position_id"], corpus, familiar_data=familiar_data)
    if selected is None or selected[0]["provenance"]["evidence_id"] != choice["evidence_id"]:
        return None, GENERAL_EMPTY
    bounds, ordered = selected[2:4]
    window = complete(
        db, db.capture_root, corpus, bounds["lower"], bounds["upper"], subject, familiar_data[1]
    )
    if window is None:
        return None, GENERAL_EMPTY
    prepared = entries(window)
    for item in ordered:
        result = _qualified(db, subject, item, selected, prepared, familiar_data[1], artifact)
        if result is not None:
            return chapter(db, subject, selected, item, result), None
    return None, GENERAL_EMPTY


def _qualified(db, subject, item, selected, prepared, games, artifact):
    entry = prepared.get(item["key"]) if item["type"] == "corpus" else None
    if entry is None or entry.get("assessment") is None:
        return None
    if exposure(db, subject, item["prompt_key"], artifact) != "not_recorded":
        return None
    source, baseline, bounds = selected[:3]
    result = assessment(db, item["version"], item["key"], source, baseline, bounds, subject, games)
    return result if result.get("context") is not None else None
