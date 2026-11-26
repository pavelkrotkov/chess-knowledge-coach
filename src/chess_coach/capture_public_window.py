"""Recheck the requested learner's exact bounded public window."""

from .capture_corpus_coverage import select_entries
from .capture_public_index import available, bind
from .deep_selection_source import learner_key
from .related_capture_public import public_candidates


def entries(db, subject, window, records, games):
    if (
        games is None
        or not available(db)
        or not isinstance(window, dict)
        or window.get("owner") != learner_key(subject)
    ):
        return None
    candidates, metadata = public_candidates(db, games)
    keys = [bind(db, item["version"], item["key"], lambda: None)[0] for item in candidates]
    if keys != window.get("keys"):
        return None
    selected = select_entries(keys, records)
    return {"entries": selected, "metadata": metadata} if selected is not None else None
