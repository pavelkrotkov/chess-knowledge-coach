"""Validate distinct project-contained recovery files and their identity."""

from pathlib import Path

from .recovery_paths import ensure_no_companions


def paths(root, source, archive, restored):
    root = Path(root).resolve(strict=True)
    files = [Path(value).resolve(strict=True) for value in (source, archive, restored)]
    if len(set(files)) != 3 or not all(
        path.is_file() and path.is_relative_to(root) for path in files
    ):
        raise ValueError("recovery files must be distinct project files")
    if len({(path.stat().st_dev, path.stat().st_ino) for path in files}) != 3:
        raise ValueError("recovery files share storage")
    ensure_no_companions(files[0])
    ensure_no_companions(files[2])
    return files


def stable(paths, before):
    for path, expected in zip(paths, before, strict=True):
        current = path.stat()
        if (
            current.st_dev,
            current.st_ino,
            current.st_size,
            current.st_mtime_ns,
            current.st_ctime_ns,
        ) != expected:
            raise ValueError("recovery file changed")


def optional(connection, root, source, archive, restored, deadline, codec):
    if archive is None and restored is None:
        return False
    if archive is None or restored is None:
        raise ValueError("both recovery files are required")
    from .native_upgrade_recovery import verify

    verify(connection, root, source, archive, restored, deadline, codec=codec)
    return True
