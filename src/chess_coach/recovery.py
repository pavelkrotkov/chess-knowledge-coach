"""Verified, non-overwriting SQLite backup and restore."""

import os
import tempfile
from pathlib import Path

from .recovery_capacity import plan
from .recovery_capacity_guard import Guard
from .recovery_copy import copy_database, pinned
from .recovery_paths import ensure_no_companions, recovery_paths
from .recovery_verify import require_standalone


def backup_database(
    source: str | Path, destination: str | Path, *, project_root: str | Path, check_only=False
):
    """Create a verified backup, or only estimate capacity for one."""
    return _copy(source, destination, project_root, check_only=check_only)


def restore_database(
    source: str | Path, destination: str | Path, *, project_root: str | Path, check_only=False
):
    """Restore a verified backup, or only estimate capacity for one."""
    return _copy(source, destination, project_root, standalone=True, check_only=check_only)


def _copy(source, destination, project_root, *, standalone=False, check_only=False):
    source_path, target = recovery_paths(source, destination, project_root)
    if standalone:
        require_standalone(source_path)
    root = Path(project_root).resolve(strict=True)
    with pinned(source_path) as (reader, deadline):
        report = plan(reader, root, target, deadline)
        # The estimate and copy refer to the same pinned source transaction.
        if check_only:
            return report
        if report["status"] != "fits":
            raise ValueError("recovery capacity unavailable; no destination was created")
        return _write(reader, deadline, root, target, report)


def _write(reader, deadline, root, target, report):
    descriptor, name = tempfile.mkstemp(prefix=".chess-recovery-", dir=target.parent)
    temporary = Path(name)
    try:
        os.close(descriptor)
        guard = Guard(root, temporary, report, deadline)
        copy_database(reader, temporary, deadline, guard)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
        guard.final()
        _publish(temporary, target)
        return target
    finally:
        temporary.unlink(missing_ok=True)


def _publish(temporary: Path, target: Path) -> None:
    directory = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
    linked = False
    try:
        ensure_no_companions(target)
        os.link(temporary, target)
        linked = True
        ensure_no_companions(target)
        os.fsync(directory)
    except BaseException as exc:
        if linked and target.exists() and os.path.samefile(temporary, target):
            target.unlink()
        if isinstance(exc, FileExistsError):
            raise FileExistsError("destination or SQLite companion already exists") from None
        raise
    finally:
        os.close(directory)
