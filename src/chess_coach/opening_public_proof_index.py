"""Hash a bounded private reference index while checking its file identity."""

import hashlib
import os
import stat
import time

MAX_INDEX_BYTES = 20_000_000


def check(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError("public preparation deadline")


def index_hash(path, deadline):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_mode & 0o077
            or before.st_size > MAX_INDEX_BYTES
        ):
            raise ValueError("public reference unavailable")
        result = hashlib.sha256()
        while chunk := stream.read(64 * 1024):
            check(deadline)
            result.update(chunk)
        after, named = os.fstat(stream.fileno()), path.stat()

    def identity(value):
        return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)

    if identity(before) != identity(after) or identity(after) != identity(named):
        raise ValueError("public reference changed")
    return result.hexdigest()
