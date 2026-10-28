"""Create and verify private project-local release directories."""

import os
import stat
from pathlib import Path


def private_directory(path: Path, *, create: bool = False) -> Path:
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError("release directory must be private and owned by the current user")
    return path


def release_paths(root: Path, commit: str) -> tuple[Path, Path, Path]:
    runtime = private_directory(root / ".runtime")
    releases = private_directory(runtime / "releases", create=True)
    release = releases / commit
    release.mkdir(mode=0o700)
    source = release / "source"
    source.mkdir(mode=0o700)
    return runtime, release, source
