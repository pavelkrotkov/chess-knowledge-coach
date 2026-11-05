"""Create or reconcile one uniquely marked private destination."""

from .study_authorization import StudyHTTPError
from .study_intent import save
from .study_inventory import inventory
from .study_privacy import _identifier, metadata
from .study_remote import StudyError


def destination(remote, path, state, account, *, before_create=lambda: None):
    found = inventory(remote, account, state["marker"])
    if state["create_pending"]:
        if len(found) != 1:
            raise StudyError("Study creation outcome remains unresolved")
        study_id = found[0]
    else:
        if found:
            raise StudyError("Study marker is already in use")
        study_id = _create(remote, path, state, before_create)
    study = metadata(remote, study_id)
    chapters = study.get("chapters")
    if study.get("name") != state["marker"] or not isinstance(chapters, list) or len(chapters) != 1:
        raise StudyError("new Study chapter inventory could not be verified")
    initial = chapters[0].get("id")
    _identifier(initial)
    state.update(study=study_id, empty_chapter=initial)
    save(path, state)


def _create(remote, path, state, before_create):
    before_create()
    state["create_pending"] = True
    save(path, state)
    try:
        before_create()
    except BaseException:
        state["create_pending"] = False
        save(path, state)
        raise
    try:
        return remote.create(state["marker"])
    except StudyHTTPError as error:
        if error.status in (401, 403, 429):
            state["create_pending"] = False
            save(path, state)
        raise
