"""Validate project-local database and private socket paths."""

import os
import stat
from pathlib import Path


def inside(root: Path, value: str, *, existing: bool) -> Path:
    path = Path(value)
    resolved = (
        path.resolve(strict=True) if existing else path.parent.resolve(strict=True) / path.name
    )
    _validate(root, resolved, existing)
    return resolved


def _validate(root: Path, resolved: Path, existing: bool) -> None:
    if not root.is_dir() or not resolved.is_relative_to(root):
        raise ValueError("browser paths must be within the selected project")
    if existing and not resolved.is_file():
        raise ValueError("browser database must already exist")
    if not existing and (resolved.exists() or resolved.is_symlink()):
        raise ValueError("browser socket path already exists")


def socket_directory(socket: Path) -> None:
    info = socket.parent.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ValueError("browser socket directory must be private and owned by the current user")
