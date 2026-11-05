"""Persist pending chapter imports and distinguish definite HTTP denials."""

from .study_authorization import StudyHTTPError
from .study_intent import save


def upload(remote, path, state, index, expected, check, *, strict):
    check()
    if strict:
        remote.guard()
    state["chapters"][index] = "pending"
    save(path, state)
    try:
        check()
        if strict:
            remote.guard()
    except BaseException:
        state["chapters"][index] = "new"
        save(path, state)
        raise
    try:
        return remote.upload(state["study"], expected)
    except StudyHTTPError as error:
        if strict and error.status in (401, 403, 429):
            state["chapters"][index] = "new"
            save(path, state)
        raise
