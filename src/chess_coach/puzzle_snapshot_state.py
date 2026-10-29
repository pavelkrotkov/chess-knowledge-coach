"""Atomic snapshot progress records."""

import json
import os
import uuid
from pathlib import Path

SOURCE_URL = "https://database.lichess.org/lichess_db_puzzle.csv.zst"


def write_state(attempt, state):
    temporary = attempt / ("state-" + uuid.uuid4().hex + ".json")
    with temporary.open("x", encoding="utf-8") as out:
        json.dump(state, out, sort_keys=True)
        out.flush()
        os.fsync(out.fileno())
    os.replace(temporary, attempt / "state.json")


def read_state(attempt):
    try:
        return json.loads((attempt / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def statuses(root):
    base = Path(root) / "puzzle-snapshots"
    if not base.is_dir():
        return []
    result = []
    for path in sorted(base.glob("*/attempt-*/state.json"))[-100:]:
        state = read_state(path.parent)
        if state:
            result.append(state)
    return result
