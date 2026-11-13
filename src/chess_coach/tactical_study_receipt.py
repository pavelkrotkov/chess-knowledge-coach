"""Validate a locally verified tactical Study receipt for private display."""

import re
from datetime import datetime

from .deep_selection_source import learner_key
from .opening_queue_files import read
from .opening_study_receipt import _chapter
from .tactical_export_input import _read
from .tactical_study_receipt_binding import timestamp, valid
from .tactical_study_receipt_chapters import entry
from .web_study_status import _link

NAME = re.compile(r"tactical-study-([0-9a-f]{64})-intent\.json")


def verified(path, expected_learner):
    match = NAME.fullmatch(path.name)
    if match is None:
        return None
    state = _read(path)
    if not valid(state, match.group(1), expected_learner):
        return None
    chapter = entry(state)
    if chapter is None:
        return None
    when = state.get("verified_at")
    moment = datetime.fromisoformat(when)
    if moment.tzinfo is None:
        return None
    link = _link(state.get("study"), chapter, when)
    return (moment, link) if link else None


def exact(directory, learner, version, course):
    state = read(directory / f"tactical-study-{version}-intent.json")
    if not isinstance(state, dict) or not valid(state, version, learner_key(learner)):
        return None
    chapter = _chapter(state, course["chapters"])
    when = state.get("verified_at")
    if chapter is None or not timestamp(when):
        return None
    return _link(state.get("study"), chapter, when)
