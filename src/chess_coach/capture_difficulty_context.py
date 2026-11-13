"""Select two ordered first-encounter capture results from one source."""

import json

from .capture_compare_scope import scope
from .capture_compare_signature import signature
from .capture_history_item import item
from .fork_followup_first import first
from .protection_progress_item import _answer, _time
from .related_capture_position import prompt_key


def _current(db, row, corpus, cache, check):
    first(db, row["subject"], row)
    entry = item(db, row, corpus, cache, check)
    if (entry["status"], entry.get("assistance"), entry.get("hints"), entry.get("reveals")) != (
        "correct",
        "unassisted",
        0,
        0,
    ):
        raise ValueError("harder capture unavailable")
    matched = scope(row, corpus)
    if matched is None:
        raise ValueError("capture context unavailable")
    return matched


def context(db, corpus, recent, earlier, check):
    cache = {}
    latest = _current(db, recent, corpus, cache, check)
    previous = _current(db, earlier, corpus, cache, check)
    if latest["key"] != previous["key"] or recent["learner_color"] != earlier["learner_color"]:
        raise ValueError("capture context changed")
    _answer(db, recent)
    if _time(_answer(db, earlier)) >= _time(recent["started_at"]):
        raise ValueError("capture ordering unavailable")
    if prompt_key(recent["prompt_fen"]) == prompt_key(earlier["prompt_fen"]):
        raise ValueError("capture positions must be distinct")
    band = latest["rating_start"] + 200
    if band >= 4000:
        raise ValueError("harder capture band unavailable")
    stored = json.loads(recent["provenance_json"])["related_capture"]["assessment"]["context"]
    expected = signature(stored, corpus, rating_start=band)
    check()
    return expected, band, recent["learner_color"]
