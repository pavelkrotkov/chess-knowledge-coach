"""Create and check bounded gzip recovery archives."""

import stat

from .recovery import _publish
from .recovery_gzip_files import digest_file, sync, temporary
from .recovery_gzip_stream import compress
from .recovery_pair_space import ARCHIVE_LIMIT, Guard, archive_limit


class ArchiveGuard(Guard):
    def check(self, remaining=0, *, force=False):
        super().check(0, force=force)


def write_archive(raw, target, metadata, root, deadline):
    limit = archive_limit(root, target, deadline)
    staged = temporary(target)
    guard = ArchiveGuard(root, target, deadline)
    raw.seek(0)
    result = compress(raw, staged, metadata, {"archive_limit_bytes": limit}, guard, deadline)
    sync(staged)
    if staged.stat().st_blocks * 512 > ARCHIVE_LIMIT:
        raise ValueError("offline archive allocation exceeds limit")
    guard.check(force=True)
    _publish(staged, target)
    staged.unlink()
    return {
        "bytes": result["archive_bytes"],
        "sha256": result["archive_sha256"],
        "raw_sha256": result["raw_sha256"],
    }


def check_archive(path, metadata, deadline):
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_size != metadata["bytes"]
        or info.st_size > ARCHIVE_LIMIT
    ):
        raise ValueError("offline archive size differs")
    if info.st_blocks * 512 > ARCHIVE_LIMIT or digest_file(path, deadline) != metadata["sha256"]:
        raise ValueError("offline archive verification failed")
