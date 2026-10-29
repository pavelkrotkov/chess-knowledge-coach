"""Lock and acquire a private immutable puzzle snapshot."""

import fcntl

from .puzzle_snapshot_boundary import checked_path
from .puzzle_snapshot_paths import version_dir
from .puzzle_snapshot_run import acquire_locked


def acquire(root, version, limits, *, client=None):
    limits.validate()
    path = version_dir(root, version)
    lock_path = checked_path(path / ".lock", path.parents[1])
    manifest = checked_path(path / "manifest.json", path.parents[1])
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if manifest.exists():
            raise FileExistsError("snapshot version is already ready")
        return acquire_locked(path, version, limits, client)
