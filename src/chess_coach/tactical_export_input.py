"""Read an explicit bounded private tactical preview."""

import json
import os
import stat
from pathlib import Path

from .web_paths import inside

MAX_BYTES = 4 * 1024 * 1024


def _read(path):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("preview must be a private owned file")
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("preview exceeds the size limit")
    return json.loads(raw)


def load(root, preview):
    root = root.resolve(strict=True)
    planning = (root / ".runtime" / "planning").resolve(strict=True)
    if not planning.is_relative_to(root):
        raise ValueError("planning directory is outside the project")
    path = Path(preview)
    if path.is_symlink():
        raise ValueError("preview must not be a symlink")
    path = inside(planning, str(path), existing=True)
    if path.parent != planning:
        raise ValueError("preview is outside the planning directory")
    return _read(path)
