"""Atomic snapshot progress records."""

import json
import os
import uuid
from pathlib import Path

from .puzzle_snapshot_boundary import checked_path
from .puzzle_snapshot_paths import existing_attempts

SOURCE_URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"


def write_state(attempt, state):
    target = checked_path(attempt / "state.json", attempt.parents[2])
    temporary = attempt / ("state-" + uuid.uuid4().hex + ".json")
    with temporary.open("x", encoding="utf-8") as out:
        json.dump(state, out, sort_keys=True)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, target)


def read_state(attempt):
    path = checked_path(attempt / "state.json", attempt.parents[2])
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def statuses(root):
    base = Path(root).resolve(strict=True) / "puzzle-snapshots"
    result = []
    for attempt in sorted(existing_attempts(base))[-100:]:
        state = read_state(attempt)
        if state:
            result.append(state)
    return result
