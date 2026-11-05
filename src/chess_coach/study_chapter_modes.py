"""Verify imported chapter modes and identify the first usable chapter."""

from .study_inventory import named
from .study_mode_policy import valid as valid_mode
from .study_privacy import _identifier, _verify
from .study_remote import StudyError
from .tactical_study_marker import require


def chapter_mode(remote, study_id, chapter_id, mode="conceal", *, marker=None):
    _identifier(study_id)
    _identifier(chapter_id)
    result = remote.request("GET", f"/study/{study_id}/{chapter_id}").json()
    study = _verify(remote, study_id, result)
    require(study, marker)
    chapter = study.get("chapter", {})
    if chapter.get("id") != chapter_id:
        raise StudyError("chapter identity could not be verified")
    valid = valid_mode(chapter, mode)
    if not valid:
        raise StudyError("chapter mode could not be verified")


def verify_modes(remote, study, state, chapters, *, marker=None):
    first = None
    for i, chapter in enumerate(chapters):
        name = named(chapter, state, i)["name"]
        found = [item["id"] for item in study["chapters"] if item.get("name") == name]
        if len(found) != 1:
            raise StudyError("chapter identity could not be verified")
        chapter_mode(
            remote, state["study"], found[0], chapter.get("mode", "conceal"), marker=marker
        )
        if first is None:
            first = found[0]
    return first
