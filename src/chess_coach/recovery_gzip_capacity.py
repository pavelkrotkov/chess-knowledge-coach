"""Reserve a separate restore before streaming a compressed backup."""

import shutil

from .recovery_capacity import MIN_WORKING, PROJECT_LIMIT, RESERVE, allocated, snapshot

MANIFEST_ALLOWANCE = 1024 * 1024


def estimate(size, root, target, deadline):
    usage = allocated(root, deadline)
    free = shutil.disk_usage(target.parent).free
    working = max(MIN_WORKING, size // 10)
    reserve = size + working + RESERVE + MANIFEST_ALLOWANCE
    archive_limit = max(0, min(PROJECT_LIMIT - usage, free) - reserve)
    return {
        "status": "conditional" if archive_limit else "insufficient",
        "snapshot_bytes": size,
        "archive_limit_bytes": archive_limit,
        "project_allocated_bytes": usage,
        "working_bytes": working,
        "reserve_bytes": RESERVE,
        "manifest_allowance_bytes": MANIFEST_ALLOWANCE,
        "project_limit_bytes": PROJECT_LIMIT,
        "filesystem_free_bytes": free,
        "scope": "Conditional: compressed size is unknown; project writers must be stopped.",
    }


def pinned_plan(reader, root, target, deadline):
    pages, page_size = snapshot(reader)
    return estimate(pages * page_size, root, target, deadline)
