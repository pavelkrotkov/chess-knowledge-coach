"""Publish an exact current opening preview through the private Study ledger."""

import os
import re
from functools import partial
from pathlib import Path

from .opening_queue_lock import lock as opening_lock
from .opening_study_current import admitted
from .opening_study_freeze import freeze
from .study_publisher import publish
from .study_session import _publish, locked
from .tactical_study_intents import MAX_INTENTS, require_clear
from .tactical_study_path import planning as private_planning
from .web_paths import inside


def _paths(root, version):
    if not re.fullmatch(r"[0-9a-f]{64}", version):
        raise ValueError("opening preview version differs")
    root = Path(root).resolve(strict=True)
    learner = os.environ["CHESS_SUBJECT"]
    planning, _ = private_planning(root, learner)
    data = (root / ".runtime" / "data").resolve(strict=True)
    if not data.is_relative_to(root):
        raise ValueError("database outside project")
    database = inside(data, os.environ["CHESS_DB"], existing=True)
    return root, learner, planning, database


def publish_locked(root, game, position, move, version):
    root, learner, planning, database = _paths(root, version)
    with (
        locked(database, planning),
        opening_lock(planning),
        admitted(database, planning, root, learner, game, position, move, version) as source,
    ):
        course, budget, check = source
        destination = planning / f"opening-study-{version}-intent.json"
        existing = require_clear(planning, destination)
        if len(existing) + (destination not in existing) > MAX_INTENTS:
            raise ValueError("too many Study intents")
        check = freeze(planning / f"opening-study-{version}-course.json", course, budget, check)
        return _publish(
            database,
            destination,
            course,
            action=partial(publish, check=check, strict=True),
            check=check,
        )
