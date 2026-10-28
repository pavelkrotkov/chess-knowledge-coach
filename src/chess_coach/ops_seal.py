"""Protect a completed release from accidental changes."""

import os
import stat
from pathlib import Path


def seal_release(release: Path) -> None:
    """Prevent accidental edits to a prepared release without following symlinks."""
    for parent, directories, files in os.walk(release, topdown=False, followlinks=False):
        for name in [*files, *directories]:
            _remove_write(Path(parent) / name)
    _remove_write(release)


def _remove_write(path: Path) -> None:
    if path.is_symlink():
        return
    info = path.stat()
    if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
        raise ValueError("release contains a hard-linked file")
    path.chmod(stat.S_IMODE(info.st_mode) & ~0o222)
