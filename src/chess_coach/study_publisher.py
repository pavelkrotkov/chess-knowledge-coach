"""Publish one marked private course without repeating uncertain creates."""

from .study_authorization import require_scopes
from .study_destination import destination
from .study_import import upload_all
from .study_intent import open_intent
from .study_privacy import metadata
from .study_remote import StudyError


def publish(remote, path, course):
    state = open_intent(path, course)
    account = remote.account()
    require_scopes(remote)
    if state["study"] is None:
        destination(remote, path, state, account)
    if metadata(remote, state["study"]).get("name") != state["marker"]:
        raise StudyError("Study marker no longer matches the publication intent")
    upload_all(remote, path, state, course["course"]["chapters"])
    return "https://lichess.org/study/" + state["study"] + "/" + state["entry_chapter"] + "#0"
