"""Verified, non-overwriting SQLite backup and restore."""

import os
import tempfile
from pathlib import Path

from .recovery_copy import copy_database
from .recovery_paths import ensure_no_companions, recovery_paths
from .recovery_verify import require_standalone


def backup_database(
    source: str | Path, destination: str | Path, *, project_root: str | Path
) -> Path:
    """Create a verified live SQLite backup without modifying the source."""
    return _copy(source, destination, project_root)


def restore_database(
    source: str | Path, destination: str | Path, *, project_root: str | Path
) -> Path:
    """Restore a verified backup to a new destination without overwriting."""
    return _copy(source, destination, project_root, standalone=True)


def _copy(
    source: str | Path,
    destination: str | Path,
    project_root: str | Path,
    *,
    standalone: bool = False,
) -> Path:
    source_path, target = recovery_paths(source, destination, project_root)
    if standalone:
        require_standalone(source_path)
    descriptor, name = tempfile.mkstemp(prefix=".chess-recovery-", dir=target.parent)
    temporary = Path(name)
    try:
        os.close(descriptor)
        copy_database(source_path, temporary)
        with temporary.open("rb") as stream:
            os.fsync(stream.fileno())
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
