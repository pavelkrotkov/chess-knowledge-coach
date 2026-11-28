"""Restore a verified offline gzip pair without the original source."""

from pathlib import Path

from .recovery import _publish
from .recovery_gzip_files import sync, temporary
from .recovery_gzip_restore import restore
from .recovery_pair_archive import check_archive
from .recovery_pair_metadata import load as load_metadata
from .recovery_pair_space import Guard, require_space
from .recovery_pair_stream import compare
from .recovery_paths import recovery_paths
from .recovery_verify import verify_standalone


def _paths(archive_a, archive_b, metadata, destination, root):
    root = Path(root).resolve(strict=True)
    a, target = recovery_paths(archive_a, destination, root)
    b, _ = recovery_paths(archive_b, destination, root)
    meta, _ = recovery_paths(metadata, destination, root)
    first, second = a.stat(), b.stat()
    if len({a, b, meta, target}) != 4 or (first.st_dev, first.st_ino) == (
        second.st_dev,
        second.st_ino,
    ):
        raise ValueError("offline pair paths must be distinct")
    if any(path.parent.stat().st_dev != first.st_dev for path in (b, meta, target)):
        raise ValueError("offline pair paths must share a filesystem")
    return root, a, b, meta, target


def restore_pair(archive_a, archive_b, metadata, destination, *, project_root, deadline):
    root, a, b, meta, target = _paths(archive_a, archive_b, metadata, destination, project_root)
    value = load_metadata(meta)
    first, second = value["archives"]
    check_archive(a, first, deadline)
    check_archive(b, second, deadline)
    size = value["raw_bytes"]
    require_space(root, target, deadline, size)
    staged = temporary(target)
    guard = Guard(root, target, deadline)
    manifest = {
        "archive_bytes": first["bytes"],
        "archive_sha256": first["sha256"],
        "raw_bytes": size,
        "raw_sha256": value["raw_sha256"],
    }
    restore(a, staged, manifest, guard, deadline)
    sync(staged)
    with staged.open("rb") as raw:
        compare(b, second, raw, size, value["raw_sha256"], deadline, deadline.check)
    verify_standalone(staged, deadline)
    guard.check(0, force=True)
    _publish(staged, target)
    staged.unlink()
    return {"status": "verified", "comparison": "complete_bytes_against_second_archive"}
