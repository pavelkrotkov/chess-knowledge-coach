"""Validate a private Study request and its local account binding."""

import os
import re

from .deep_selection_source import learner_key
from .learner_identity import normalize_identity
from .opening_study_session import _paths
from .recurrence_cursor import _valid_id


def credentials(root, db, learner, version):
    try:
        _, subject, _, database = _paths(root, version)
        return bool(
            os.environ.get("LICHESS_STUDY_TOKEN", "").strip()
            and normalize_identity(subject) == normalize_identity(learner)
            and database == db.path.resolve(strict=True)
        )
    except (ValueError, OSError, KeyError):
        return False


def _revision(selection):
    return (
        _valid_id(selection["game_id"])
        and _valid_id(selection["position_id"])
        and isinstance(selection["move"], str)
        and re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbn]?", selection["move"]) is not None
    )


def _selection(selection):
    if set(selection) == {"game_id", "position_id", "move"}:
        return _revision(selection)
    return (
        set(selection) == {"color", "parent", "move"}
        and all(isinstance(value, str) and value for value in selection.values())
        and selection.get("color") in {"white", "black"}
    )


def valid(item, database, learner):
    if not isinstance(item, dict) or not isinstance(item.get("selection"), dict):
        return False
    selection = item["selection"]
    version = item.get("version")
    return all(
        (
            item.get("database") == database,
            item.get("owner") == learner_key(learner),
            item.get("state") in {"queued", "incomplete", "stale", "complete"},
            _selection(selection),
            isinstance(version, str) and re.fullmatch(r"[0-9a-f]{64}", version) is not None,
        )
    )
