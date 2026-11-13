"""Read and validate a privately offered tactical course."""

import re
from pathlib import Path
from types import SimpleNamespace

from .deep_selection_source import learner_key
from .opening_queue_files import read
from .opening_queue_location import location
from .tactical_course_offer import SLOT, VERSION
from .tactical_export_contract import contract, validate
from .tactical_export_input import load
from .tactical_study_preview import preview
from .tactical_study_receipt_binding import timestamp


def _item(item, identity, subject):
    if not isinstance(item, dict) or (
        item.get("version"),
        item.get("database"),
        item.get("owner"),
    ) != (VERSION, identity, learner_key(subject)):
        raise ValueError("prepared course unavailable")
    name, version, when = item.get("file"), item.get("hash"), item.get("prepared_at")
    if (
        not isinstance(name, str)
        or re.fullmatch(r"[^/\\]{1,255}", name) is None
        or not isinstance(version, str)
        or re.fullmatch(r"[0-9a-f]{64}", version) is None
        or not timestamp(when)
    ):
        raise ValueError("prepared course unavailable")
    return name, version


def offered(root, database, subject, corpus):
    directory, identity = location(SimpleNamespace(path=database), root, subject)
    item = read(directory / SLOT)
    name, version = _item(item, identity, subject)
    envelope = load(Path(root), directory / name)
    saved = preview(envelope, version)
    body = validate(saved, corpus)
    exported = envelope["export"]
    if (exported.get("kind"), exported.get("policy")) != contract(body):
        raise ValueError("prepared export differs")
    return item, exported
