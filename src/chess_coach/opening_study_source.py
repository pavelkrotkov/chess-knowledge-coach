"""Track opening inputs that can change outside the game database."""

from pathlib import Path

from .opening_profile_index import INDEX_NAME
from .opening_queue_artifact import path as result_path
from .opening_queue_binding import ENGINE
from .opening_queue_failure import path as failure_path


def _stat(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    return [
        info.st_dev,
        info.st_ino,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
        info.st_mode,
        info.st_uid,
    ]


def inputs(directory, identity, root):
    selected = [{"id": identity, "attempt": attempt} for attempt in range(3)]
    engine = Path(ENGINE)
    config = Path(root) / ".runtime" / "config.env"
    return [
        directory / "opening-comparison-slot.json",
        directory / INDEX_NAME,
        config,
        config.resolve(),
        *(result_path(directory, item) for item in selected),
        *(failure_path(directory, item) for item in selected),
        engine,
        engine.resolve(),
    ]


def fingerprint(paths):
    return [_stat(path) for path in paths]
