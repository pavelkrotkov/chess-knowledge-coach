"""Read only a matching strict private Study receipt."""

from .deep_selection_source import learner_key
from .opening_queue_files import read
from .opening_unfamiliar_study_course import build
from .tactical_study_receipt_binding import timestamp, valid
from .tactical_study_receipt_chapters import entry
from .web_study_status import _link


def link(directory, learner, course):
    return verified(directory, learner, course["version"], build(course, course["version"]))


def verified(directory, learner, version, body):
    state = read(directory / f"opening-study-{version}-intent.json")
    if state is None:
        return None
    chapters = body["course"]["chapters"]
    if not valid(state, body["course_sha256"], learner_key(learner)):
        return None
    chapter = _chapter(state, chapters)
    if chapter is None:
        return None
    when = state.get("verified_at")
    if not timestamp(when):
        return None
    value = _link(state.get("study"), chapter, when)
    return value["url"] if value else None


def _chapter(state, chapters):
    chapter = entry(state)
    if chapter is None or len(state["chapter_ids"]) != len(chapters):
        return None
    if state["chapter_modes"] != [item["mode"] for item in chapters]:
        return None
    return chapter
