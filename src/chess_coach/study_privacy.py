"""Verify Study owner, visibility and restrictions before private uploads."""

import re

from .learner_identity import normalize_identity
from .study_remote import SETTINGS, StudyError


def metadata(remote, study_id):
    _identifier(study_id)
    result = remote.request("GET", f"/study/{study_id}", params={"chapters": "1"}).json()
    return _verify(remote, study_id, result)


def _identifier(value):
    if not isinstance(value, str) or re.fullmatch(r"[A-Za-z0-9]{8}", value) is None:
        raise StudyError("invalid Study identifier")


def _verify(remote, study_id, result):
    study = result.get("study", {})
    if study.get("id") != study_id or normalize_identity(study.get("ownerId")) != remote.learner:
        raise StudyError("Study ownership could not be verified")
    if study.get("visibility") != "private":
        raise StudyError("Study privacy could not be verified")
    settings = study.get("settings", {})
    if any(settings.get(key) != value for key, value in SETTINGS.items()):
        raise StudyError("Study restrictions could not be verified")
    return study
