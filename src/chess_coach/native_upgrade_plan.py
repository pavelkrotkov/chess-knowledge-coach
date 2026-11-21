"""Read-only, bounded native-upgrade inventory; this does not authorize migration."""

import sqlite3
import time
from subprocess import SubprocessError

from .native_upgrade_inventory import inventory
from .native_upgrade_layout import inspect as inspect_layout
from .native_upgrade_recovery_paths import optional as check_recovery
from .native_upgrade_source import path, unchanged
from .recovery_capacity import PROJECT_LIMIT, RESERVE, allocated
from .recovery_copy import pinned
from .recovery_deadline import Deadline
from .recovery_fidelity import MAX_RECORD_BYTES

INVENTORY_SECONDS = 60


def _inspect(connection, source, root, deadline):
    until = min(time.monotonic() + INVENTORY_SECONDS, deadline.end)
    connection.set_progress_handler(lambda: int(time.monotonic() >= until), 1000)
    connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_RECORD_BYTES)
    try:
        layout = inspect_layout(connection, source)
        counts = inventory(connection)
        if time.monotonic() >= until:
            raise TimeoutError("inventory deadline reached")
    finally:
        connection.set_progress_handler(deadline.progress, 1000)
    return {
        "status": "unknown",
        "inventory_complete": True,
        "recovery_current": False,
        **layout,
        **counts,
        "project_allocated_bytes": allocated(root, deadline),
        "project_limit_bytes": PROJECT_LIMIT,
        "operating_reserve_bytes": RESERVE,
        "scope": "Read-only inventory and optional recovery check; allocated peak and migration admission remain unverified.",
    }


def plan(source, project_root, *, archive=None, restored=None, codec="gzip"):
    """Inspect without initializing, migrating, or creating source artifacts."""
    deadline = Deadline()
    try:
        source, root = path(source, project_root)
        before = source.stat()
        with pinned(source, deadline, require_memory=True) as connection:
            connection.execute("PRAGMA query_only=ON")
            report = _inspect(connection, source, root, deadline)
            if check_recovery(connection, root, source, archive, restored, deadline, codec):
                report["recovery_current"] = True
                report["project_allocated_bytes"] = allocated(root, deadline)
            unchanged(source, before)
            return report
    except (
        sqlite3.Error,
        ValueError,
        TimeoutError,
        OSError,
        MemoryError,
        SubprocessError,
        RuntimeError,
        TypeError,
    ):
        return {"status": "unknown", "inventory_complete": False}
