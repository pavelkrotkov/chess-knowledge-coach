"""Validate and safely replace a private tactical Study request slot."""

import re

from .deep_selection_source import learner_key
from .opening_queue_files import read


def valid(item, database, learner):
    if not isinstance(item, dict):
        return False
    version, name = item.get("version"), item.get("file")
    return all(
        (
            item.get("database") == database,
            item.get("owner") == learner_key(learner),
            item.get("state") in {"queued", "incomplete", "stale", "complete"},
            item.get("turn") in {"opening", "tactical"},
            isinstance(item.get("corpus"), str),
            isinstance(version, str) and re.fullmatch(r"[0-9a-f]{64}", version) is not None,
            isinstance(name, str) and re.fullmatch(r"[^/\\]{1,255}", name) is not None,
        )
    )


def replaceable(directory, old, item, database, learner):
    if old is None:
        return True
    if not valid(old, database, learner):
        raise ValueError("Study request unavailable")
    if (old["version"], old["file"]) == (item["version"], item["file"]):
        return False
    intent = directory / f"tactical-study-{old['version']}-intent.json"
    if intent.exists() and (read(intent) or {}).get("complete") is not True:
        raise ValueError("Earlier Study request remains incomplete")
    return True
