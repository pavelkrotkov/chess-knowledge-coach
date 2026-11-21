"""Validate a stable, project-contained SQLite source."""

from pathlib import Path

from .recovery_paths import ensure_no_companions


def path(source, root):
    root = Path(root).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    if not root.is_dir() or not source.is_file() or not source.is_relative_to(root):
        raise ValueError("source database must be inside the project")
    ensure_no_companions(source)
    return source, root


def unchanged(source, before):
    after = source.stat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        raise ValueError("database identity changed")
    ensure_no_companions(source)
