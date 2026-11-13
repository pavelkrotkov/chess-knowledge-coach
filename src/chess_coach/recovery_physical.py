"""Estimate recovery capacity without opening the source in SQLite."""

import shutil
import stat
from pathlib import Path

from .recovery_capacity import MIN_WORKING, PROJECT_LIMIT, RESERVE, allocated


def _file_state(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("recovery source file unavailable")
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def physical(source, root, target, deadline):
    """Estimate capacity using only stable file metadata, with no SQLite open."""
    wal = Path(str(source) + "-wal")
    before = (_file_state(source), _file_state(wal))
    if before[0] is None:
        raise ValueError("recovery source file unavailable")
    with source.open("rb") as stream:
        header = stream.read(20)
    if len(header) < 20 or header[:16] != b"SQLite format 3" + bytes([0]):
        raise ValueError("source is not a valid SQLite database")
    # A WAL may contain repeated pages, so its length can overestimate the snapshot.
    size = before[0][2] + (before[1][2] if before[1] else 0)
    working = max(MIN_WORKING, size // 10)
    usage = allocated(root, deadline)
    free = shutil.disk_usage(target.parent).free
    # Do not present a stable estimate when source files moved during the scan.
    if before != (_file_state(source), _file_state(wal)):
        raise ValueError("recovery source changed during capacity check")
    required = size + working + RESERVE
    return {
        "status": "fits"
        if usage + required <= PROJECT_LIMIT and free >= required
        else "insufficient",
        "estimated_snapshot_bytes": size,
        "project_allocated_bytes": usage,
        "working_bytes": working,
        "reserve_bytes": RESERVE,
        "project_limit_bytes": PROJECT_LIMIT,
        "filesystem_free_bytes": free,
        "scope": "Unpinned physical file-size estimate, not a quota or verified backup; the actual copy checks a pinned snapshot.",
    }
