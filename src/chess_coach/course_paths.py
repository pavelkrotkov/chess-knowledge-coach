"""Constrain course inputs and outputs to the private selected project."""

import os

from .web_paths import inside, socket_directory


def paths(root, preview, target, *, output):
    root = root.resolve(strict=True)
    planning = (root / ".runtime" / "planning").resolve(strict=True)
    data = (root / ".runtime" / "data").resolve(strict=True)
    if not planning.is_relative_to(root) or not data.is_relative_to(root):
        raise ValueError("course paths escape the project")
    socket_directory(root / ".runtime" / "entry")
    if planning.stat().st_uid != os.getuid() or planning.stat().st_mode & 0o022:
        raise ValueError("planning directory must be owned and not group-writable")
    database = inside(data, os.environ["CHESS_DB"], existing=True)
    preview = inside(planning, str(preview), existing=True)
    target = inside(planning, str(target), existing=not output)
    return database, planning, preview, target
