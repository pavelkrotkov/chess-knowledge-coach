"""Validate and prepare a pinned source and its two offline archives."""

import os
import stat
from pathlib import Path

from .recovery_gzip_snapshot import identity, pinned_raw
from .recovery_pair_archive import write_archive
from .recovery_paths import recovery_paths


def paths(source, archive_a, archive_b, restored, root):
    root = Path(root).resolve(strict=True)
    if Path(source).is_symlink():
        raise ValueError("offline source must not be a symlink")
    source, a = recovery_paths(source, archive_a, root)
    _, b = recovery_paths(source, archive_b, root)
    _, target = recovery_paths(source, restored, root)
    _, meta = recovery_paths(source, str(a) + ".pair.json", root)
    if len({source, a, b, target, meta}) != 5:
        raise ValueError("offline recovery paths must be distinct")
    device = source.stat().st_dev
    if any(path.parent.stat().st_dev != device for path in (a, b, target, meta)):
        raise ValueError("offline recovery paths must share a filesystem")
    return root, source, a, b, target, meta


def create_pair(source, a, b, root, deadline):
    with pinned_raw(source, deadline) as (_, raw, metadata):
        info = os.fstat(raw.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("offline source must have exactly one link")
        original = identity(info)
        first = write_archive(raw, a, metadata, root, deadline)
        second = write_archive(raw, b, metadata, root, deadline)
        if first["raw_sha256"] != second["raw_sha256"]:
            raise ValueError("offline source changed during archive creation")
        if identity(os.fstat(raw.fileno())) != original:
            raise ValueError("offline source changed during archive creation")
    return metadata, original, first, second, info.st_blocks * 512
