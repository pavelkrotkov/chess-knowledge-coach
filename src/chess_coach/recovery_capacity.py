"""Conservatively bound project and destination space for a SQLite copy."""

import shutil
import subprocess
import time

PROJECT_LIMIT = 10 * 1024**3
RESERVE = 64 * 1024**2
MIN_WORKING = 64 * 1024**2


def snapshot(reader):
    # Page count includes free pages and reflects the already pinned view.
    pages = reader.execute("PRAGMA page_count").fetchone()[0]
    page_size = reader.execute("PRAGMA page_size").fetchone()[0]
    if (
        not isinstance(pages, int)
        or pages < 1
        or page_size not in {512, 1024, 2048, 4096, 8192, 16384, 32768, 65536}
    ):
        raise ValueError("database size unavailable")
    return pages, page_size


def allocated(root, deadline):
    remaining = deadline.end - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("database snapshot time limit exceeded")
    # Include nested mounts; an incomplete tree measurement must fail closed.
    result = subprocess.run(
        ["du", "-sk", str(root)],
        check=True,
        capture_output=True,
        text=True,
        timeout=min(8, remaining),
    )
    return int(result.stdout.split()[0]) * 1024


def plan(reader, root, target, deadline):
    pages, page_size = snapshot(reader)
    size = pages * page_size
    working = max(MIN_WORKING, size // 10)
    usage = allocated(root, deadline)
    free = shutil.disk_usage(target.parent).free
    required = size + working + RESERVE
    return {
        "status": "fits"
        if usage + required <= PROJECT_LIMIT and free >= required
        else "insufficient",
        "snapshot_bytes": size,
        "page_count": pages,
        "page_size": page_size,
        "project_allocated_bytes": usage,
        "working_bytes": working,
        "reserve_bytes": RESERVE,
        "project_limit_bytes": PROJECT_LIMIT,
        "filesystem_free_bytes": free,
        "scope": "Point-in-time estimate; concurrent writes are not controlled by a quota.",
    }
