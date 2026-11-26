"""Recheck the requested learner's exact bounded public window."""

from .capture_corpus_coverage import select_entries
from .capture_public_index import available, bind
from .deep_selection_source import learner_key
from .related_capture_public import public_candidates


def _published(window, owner, keys):
    if window is None:
        return True
    public = window.get("public") if isinstance(window, dict) else None
    return isinstance(public, dict) and public.get("owner") == owner and public.get("keys") == keys


def entries(db, subject, window, records, games):
    if games is None or not available(db) or not learner_key(subject):
        return None
    candidates, metadata = public_candidates(db, games)
    keys = [bind(db, item["version"], item["key"], lambda: None)[0] for item in candidates]
    if not _published(window, learner_key(subject), keys):
        return None
    selected = select_entries(keys, records)
    return {"entries": selected, "metadata": metadata} if selected is not None else None
