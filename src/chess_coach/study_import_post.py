"""Persist pending chapter imports and distinguish definite HTTP denials."""

from .study_authorization import StudyHTTPError
from .study_intent import save
from .tactical_study_exposure import begin, clear


def upload(remote, path, state, index, expected, check, *, strict):
    check()
    if strict:
        remote.guard()
    begin(state, index, expected)
    state["chapters"][index] = "pending"
    save(path, state)
    try:
        check()
        if strict:
            remote.guard()
    except BaseException:
        state["chapters"][index] = "new"
        clear(state, index)
        save(path, state)
        raise
    try:
        return remote.upload(state["study"], expected)
    except StudyHTTPError as error:
        if strict and error.status in (401, 403, 429):
            state["chapters"][index] = "new"
            clear(state, index)
            save(path, state)
        raise
