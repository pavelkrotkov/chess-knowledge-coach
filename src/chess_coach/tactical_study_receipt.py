"""Validate a locally verified tactical Study receipt for private display."""

import re
from datetime import datetime

from .tactical_export_input import _read
from .tactical_study_receipt_binding import valid
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
