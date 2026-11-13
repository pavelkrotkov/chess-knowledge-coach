"""Estimate recovery capacity without opening the source in SQLite."""

import shutil
import stat
from pathlib import Path

from .recovery_capacity import MIN_WORKING, PROJECT_LIMIT, RESERVE, allocated

SOURCE_ALLOWANCE = 1024**2


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
    usage = allocated(root, deadline)
    free = shutil.disk_usage(target.parent).free
    after = (_file_state(source), _file_state(wal))
    changed = before != after
    # Compare the smaller estimate when the source moved during measurement.
    size = min(_size(before), _size(after)) if after[0] else _size(before)
    working = max(MIN_WORKING, size // 10)
    required = size + working + RESERVE + SOURCE_ALLOWANCE
    fits = usage + required <= PROJECT_LIMIT and free >= required
    deadline.check()
    return {
        "status": _status(changed, after[0] is not None, fits),
        "source_changed": changed,
        "estimated_snapshot_bytes": size,
        "project_allocated_bytes": usage,
        "working_bytes": working,
        "reserve_bytes": RESERVE,
        "source_sidecar_allowance_bytes": SOURCE_ALLOWANCE,
        "project_limit_bytes": PROJECT_LIMIT,
        "filesystem_free_bytes": free,
        "scope": "Unpinned physical file-size estimate, not a quota or verified backup; the actual copy checks a pinned snapshot. If unavailable, retry after the source settles.",
    }


def _size(state):
    # WAL length includes repeated frames and can overestimate the snapshot.
    return state[0][2] + (state[1][2] if state[1] else 0)


def _status(changed, present, fits):
    if not present:
        return "unavailable"
    if not fits:
        return "insufficient"
    return "unavailable" if changed else "fits"
