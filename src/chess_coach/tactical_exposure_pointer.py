"""Find the exact owner-bound retained tactical artifact."""

import re

from .deep_selection_source import learner_key
from .opening_queue_files import read
from .tactical_course_offer import SLOT as OFFER_SLOT
from .tactical_course_offer import STUDY_SLOT


def pointer(directory, database, subject, version):
    for slot in (OFFER_SLOT, STUDY_SLOT):
        item = read(directory / slot)
        if not isinstance(item, dict):
            continue
        actual = (item.get("owner"), item.get("database"), item.get("hash") or item.get("version"))
        if actual != (learner_key(subject), database, version):
            continue
        name = item.get("file")
        if isinstance(name, str) and re.fullmatch(r"[^/\\]{1,255}", name):
            return directory / name
    return None
