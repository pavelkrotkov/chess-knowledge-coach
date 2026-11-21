"""Restore a retained gzip backup without requiring the original database."""

import sqlite3
from contextlib import closing
from pathlib import Path

from .recovery import _publish
from .recovery_deadline import Deadline
from .recovery_gzip_capacity import restore_plan
from .recovery_gzip_files import sync, temporary
from .recovery_gzip_guard import Guard
from .recovery_gzip_manifest import load, verify_metadata
from .recovery_gzip_memory import configure, probe
from .recovery_gzip_restore import restore
from .recovery_paths import recovery_paths
from .recovery_verify import require_standalone, verify_database


def restore_backup(archive, destination, *, project_root, check_only=False):
    root = Path(project_root).resolve(strict=True)
    archive, target = recovery_paths(archive, destination, root)
    manifest = load(archive)
    probe()
    deadline = Deadline()
    report = restore_plan(manifest["raw_bytes"], root, target, deadline)
    if check_only:
        return report
    if report["status"] != "fits":
        raise ValueError("recovery capacity unavailable; no destination was created")
    return _write(archive, target, root, manifest, report, deadline)


def _write(archive, target, root, manifest, report, deadline):
    staged = temporary(target)
    try:
        guard = Guard(root, target, report, deadline)
        guard.check(manifest["raw_bytes"], force=True)
        restore(archive, staged, manifest, guard, deadline)
        sync(staged)
        require_standalone(staged)
        with closing(sqlite3.connect(staged.as_uri() + "?mode=ro", uri=True, timeout=5)) as reader:
            reader.set_progress_handler(deadline.progress, 1000)
            reader.execute("PRAGMA query_only=ON")
            configure(reader)
            verify_metadata(reader, manifest)
            verify_database(reader)
        guard.check(0, force=True)
        _publish(staged, target)
        return {"status": "verified"}
    finally:
        staged.unlink(missing_ok=True)
