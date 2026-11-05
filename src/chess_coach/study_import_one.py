"""Import or reconcile one Study chapter without blind retries."""

from .study_import_post import upload
from .study_intent import save
from .study_inventory import named, verify_chapters
from .study_privacy import metadata
from .study_remote import StudyError
from .tactical_study_mode import verify as verify_mode
from .tactical_study_order import verify as verify_order


def _inventory(remote, state, chapters, strict):
    study = metadata(remote, state["study"])
    verify_chapters(study, state, None)
    if strict:
        verify_order(study, state, chapters)
    return study


def _unresolved(study, state, expected, index):
    if any(item.get("name") == expected["name"] for item in study["chapters"]):
        raise StudyError("chapter name already exists with different content")
    if state["chapters"][index] != "new":
        raise StudyError("chapter import outcome remains unresolved")


def upload_one(remote, path, state, chapter, index, chapters, check, match, strict):
    study = _inventory(remote, state, chapters, strict)
    expected = named(chapter, state, index)
    exported = remote.export(state["study"])
    if match(expected, exported):
        if strict:
            verify_mode(remote, study, state, chapters, index)
        check()
        state["chapters"][index] = "done"
        save(path, state)
        return
    _unresolved(study, state, expected, index)
    response = upload(remote, path, state, index, expected, check, strict=strict)
    if response.get("error") or len(response.get("chapters", [])) != 1:
        raise StudyError("chapter import outcome remains unresolved")
    study = _inventory(remote, state, chapters, strict)
    if not match(expected, remote.export(state["study"])):
        raise StudyError("chapter read-back did not match")
    if strict:
        verify_mode(remote, study, state, chapters, index)
    check()
    state["chapters"][index] = "done"
    save(path, state)
