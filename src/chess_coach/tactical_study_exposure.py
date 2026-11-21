"""Bind possible and verified tactical chapter delivery to the existing intent."""

from datetime import UTC, datetime

from .deep_selection_source import learner_key
from .fact_fingerprint import digest
from .study_remote import StudyError
from .tactical_study_exposure_prepare import begin

VERSION = "tactical-study-exposure-v1"


def bind(state, learner):
    owner = learner_key(learner)
    existing = state.get("tactical_delivery")
    if existing is None:
        state["tactical_delivery"] = {"version": VERSION, "owner": owner, "chapters": {}}
    elif existing.get("version") != VERSION or existing.get("owner") != owner:
        raise StudyError("tactical exposure owner unavailable")


def clear(state, index):
    delivery = state.get("tactical_delivery")
    if delivery is not None:
        delivery["chapters"].pop(str(index), None)


def verified(state, index, chapter):
    delivery = state.get("tactical_delivery")
    if delivery is None:
        return
    entry = delivery["chapters"].get(str(index))
    if entry is None:
        begin(state, index, chapter)
        entry = delivery["chapters"][str(index)]
        entry["pending_at"] = None
    if entry["chapter_hash"] != digest(chapter["pgn"]):
        raise StudyError("tactical exposure chapter changed")
    if entry["verified_at"] is None:
        entry["verified_at"] = datetime.now(UTC).isoformat()
