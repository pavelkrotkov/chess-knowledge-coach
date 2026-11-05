"""Publish one marked private course without repeating uncertain creates."""

from .study_authorization import require_scopes
from .study_destination import destination
from .study_import import upload_all
from .study_intent import open_intent
from .study_privacy import metadata
from .study_remote import StudyError
from .tactical_study_intents import require_clear
from .tactical_study_ledger import validate


def publish(remote, path, course, *, check=lambda: None, strict=False):
    check()
    state = open_intent(path, course)
    if strict:
        validate(state, course["course"]["chapters"])
    account = remote.account()
    require_scopes(remote)
    if state["study"] is None:

        def before_create():
            require_clear(path.parent, path)
            check()

        destination(remote, path, state, account, before_create=before_create)
    if metadata(remote, state["study"]).get("name") != state["marker"]:
        raise StudyError("Study marker no longer matches the publication intent")
    upload_all(remote, path, state, course["course"]["chapters"], check=check, strict=strict)
    return "https://lichess.org/study/" + state["study"] + "/" + state["entry_chapter"] + "#0"
