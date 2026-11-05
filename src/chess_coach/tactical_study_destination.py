"""Prepare one private tactical destination without uploading chapters."""

from .study_authorization import require_scopes
from .study_destination import destination
from .study_intent import open_intent
from .study_inventory import verify_chapters
from .study_privacy import metadata
from .study_remote import StudyError
from .tactical_study_intents import require_clear


def prepare(remote, path, course, *, check=lambda: None):
    check()
    state = open_intent(path, course)
    account = remote.account()
    require_scopes(remote)
    if state["study"] is None:

        def before_create():
            require_clear(path.parent, path)
            check()

        destination(remote, path, state, account, before_create=before_create)
    study = metadata(remote, state["study"])
    if study.get("name") != state["marker"]:
        raise StudyError("Study marker no longer matches the publication intent")
    verify_chapters(study, state, [])
    return state["study"]
