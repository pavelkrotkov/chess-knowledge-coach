"""Pin one standalone rollback-journal source without dropping its read lock."""

import os
import stat
from contextlib import contextmanager
from pathlib import Path

from .recovery_capacity import snapshot
from .recovery_copy import pinned
from .recovery_verify import verify_database


def _companions(source):
    for suffix in ("-wal", "-shm", "-journal"):
        path = Path(str(source) + suffix)
        if path.exists() or path.is_symlink():
            raise ValueError("compressed recovery requires a standalone database")


def _metadata(reader, raw, source):
    if reader.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
        raise ValueError("compressed recovery requires DELETE journal mode")
    _companions(source)
    pages, page_size = snapshot(reader)
    info, current = os.fstat(raw.fileno()), source.stat()
    if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) != (
        current.st_dev,
        current.st_ino,
    ):
        raise ValueError("compressed recovery source changed")
    if info.st_size != pages * page_size:
        raise ValueError("compressed recovery source size differs from snapshot")
    header = raw.read(20)
    raw.seek(0)
    if len(header) != 20 or header[:16] != b"SQLite format 3\x00" or header[18:20] != b"\x01\x01":
        raise ValueError("compressed recovery requires a standalone database")
    verify_database(reader)
    return {
        "page_count": pages,
        "page_size": page_size,
        "raw_bytes": info.st_size,
        "user_version": reader.execute("PRAGMA user_version").fetchone()[0],
        "application_id": reader.execute("PRAGMA application_id").fetchone()[0],
        "encoding": reader.execute("PRAGMA encoding").fetchone()[0],
    }


@contextmanager
def pinned_raw(source, deadline):
    _companions(source)
    descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    # Closing any other descriptor for this inode before SQLite closes can release
    # POSIX locks. Keep the raw descriptor open outside the SQLite context.
    with os.fdopen(descriptor, "rb") as raw, pinned(source, deadline) as reader:
        metadata = _metadata(reader, raw, source)
        yield reader, raw, metadata
