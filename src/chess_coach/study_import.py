"""Import one chapter at a time and reconcile every uncertain outcome."""

from datetime import UTC, datetime

from .study_intent import save
from .study_inventory import named, verify_chapters, verify_modes
from .study_pgn_verify import matches
from .study_privacy import metadata
from .study_remote import StudyError


def upload_all(remote, path, state, chapters):
    for index, chapter in enumerate(chapters):
        _upload(remote, path, state, chapter, index)
    study = metadata(remote, state["study"])
    verify_chapters(study, state, chapters)
    exported = remote.export(state["study"])
    if not all(matches(named(chapter, state, i), exported) for i, chapter in enumerate(chapters)):
        raise StudyError("Study read-back is incomplete")
    verify_modes(remote, study, state, chapters)
    state["complete"] = True
    state["verified_at"] = datetime.now(UTC).isoformat()
    save(path, state)


def _upload(remote, path, state, chapter, index):
    study = metadata(remote, state["study"])
    verify_chapters(study, state, None)
    expected = named(chapter, state, index)
    exported = remote.export(state["study"])
    if matches(expected, exported):
        state["chapters"][index] = "done"
        save(path, state)
        return
    if any(item.get("name") == expected["name"] for item in study["chapters"]):
        raise StudyError("chapter name already exists with different content")
    if state["chapters"][index] != "new":
        raise StudyError("chapter import outcome remains unresolved")
    state["chapters"][index] = "pending"
    save(path, state)
    response = remote.upload(state["study"], expected)
    if response.get("error") or len(response.get("chapters", [])) != 1:
        raise StudyError("chapter import outcome remains unresolved")
    study = metadata(remote, state["study"])
    verify_chapters(study, state, None)
    if not matches(expected, remote.export(state["study"])):
        raise StudyError("chapter read-back did not match")
    state["chapters"][index] = "done"
    save(path, state)
