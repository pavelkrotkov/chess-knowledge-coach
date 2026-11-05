"""Verify a tactical Study inventory is an exact ordered prefix."""

from .study_inventory import named
from .study_privacy import _identifier
from .study_remote import StudyError
from .tactical_study_marker import require


def verify(study, state, chapters, *, complete=False):
    require(study, state["marker"])
    _identifier(state["empty_chapter"])
    items = study.get("chapters")
    if not isinstance(items, list) or not items or items[0].get("id") != state["empty_chapter"]:
        raise StudyError("initial Study chapter order changed")
    actual = items[1:]
    if len(actual) > len(chapters) or (complete and len(actual) != len(chapters)):
        raise StudyError("Study chapter inventory is incomplete")
    ids = _ids(actual, state, chapters)
    if len(set([*ids, state["empty_chapter"]])) != len(ids) + 1:
        raise StudyError("Study chapter identity is ambiguous")
    return ids


def _ids(actual, state, chapters):
    ids = []
    for index, item in enumerate(actual):
        if (
            not isinstance(item, dict)
            or item.get("name") != named(chapters[index], state, index)["name"]
        ):
            raise StudyError("Study chapter order changed")
        _identifier(item.get("id"))
        ids.append(item["id"])
    return ids
