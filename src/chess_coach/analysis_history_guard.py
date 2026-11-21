"""Connection, deadline and disk guards for analysis-history conversion."""

import shutil
import time
from pathlib import Path

from .recovery_capacity import PROJECT_LIMIT, RESERVE, allocated


def check_storage(source, root, report, deadline):
    deadline.check()
    journal = Path(str(source) + "-journal")
    growth = max(0, source.stat().st_size - report["physical_file_bytes"])
    if journal.exists():
        growth += max(journal.stat().st_size, journal.stat().st_blocks * 512)
    limit = report["replacement_and_index_bound_bytes"] + report["rollback_journal_bound_bytes"]
    if growth > limit or shutil.disk_usage(source.parent).free < RESERVE:
        raise ValueError("conversion storage bound exceeded")
    if allocated(root, deadline) + RESERVE > PROJECT_LIMIT:
        raise ValueError("project storage reserve unavailable")


def progress(source, root, report, deadline):
    next_check = time.monotonic() + 2

    def check():
        nonlocal next_check
        if deadline.progress():
            return 1
        if time.monotonic() < next_check:
            return 0
        try:
            check_storage(source, root, report, deadline)
        except (OSError, ValueError, TimeoutError):
            return 1
        next_check = time.monotonic() + 30
        return 0

    return check
