"""Validate a private Study request and its local account binding."""

import os
import re

from .curriculum_cursor_capture import _digest
from .deep_selection_source import learner_key
from .learner_identity import normalize_identity
from .opening_study_session import _paths
from .opening_unfamiliar_selection import _valid as valid_unfamiliar
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
    if set(selection) == {"context_choice"}:
        return _digest(selection["context_choice"])
    return valid_unfamiliar(selection)


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
            _digest(version),
        )
    )
