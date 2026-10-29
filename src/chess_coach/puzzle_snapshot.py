"""Lock and acquire a private immutable puzzle snapshot."""

import fcntl

from .puzzle_snapshot_paths import version_dir
from .puzzle_snapshot_run import acquire_locked


def acquire(root, version, limits, *, client=None):
    limits.validate()
    path = version_dir(root, version)
    with (path / ".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (path / "manifest.json").exists():
            raise FileExistsError("snapshot version is already ready")
        return acquire_locked(path, version, limits, client)
