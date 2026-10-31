"""Create or reconcile one uniquely marked private destination."""

from .study_intent import save
from .study_inventory import inventory
from .study_privacy import metadata
from .study_remote import StudyError


def destination(remote, path, state, account):
    found = inventory(remote, account, state["marker"])
    if state["create_pending"]:
        if len(found) != 1:
            raise StudyError("Study creation outcome remains unresolved")
        study_id = found[0]
    else:
        if found:
            raise StudyError("Study marker is already in use")
        state["create_pending"] = True
        save(path, state)
        study_id = remote.create(state["marker"])
    study = metadata(remote, study_id)
    chapters = study.get("chapters")
    if study.get("name") != state["marker"] or not isinstance(chapters, list) or len(chapters) != 1:
        raise StudyError("new Study chapter inventory could not be verified")
    initial = chapters[0].get("id")
    if not isinstance(initial, str):
        raise StudyError("initial chapter could not be verified")
    state.update(study=study_id, empty_chapter=initial)
    save(path, state)
