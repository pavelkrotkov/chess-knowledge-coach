"""Stream and authenticate a gzip archive and its separate restored file."""

import gzip
import hashlib

from .recovery_gzip_files import digest_file

CHUNK = 64 * 1024


class LimitedOutput:
    def __init__(self, stream, limit):
        self.stream = stream
        self.limit = limit
        self.size = 0

    def write(self, value):
        if self.size + len(value) > self.limit:
            raise ValueError("compressed backup exceeded its reserved space")
        written = self.stream.write(value)
        if written != len(value):
            raise OSError("compressed backup write incomplete")
        self.size += written
        return written

    def flush(self):
        self.stream.flush()


def compress(raw, archive, metadata, report, guard, deadline):
    digest = hashlib.sha256()
    total = 0
    with archive.open("wb", buffering=0) as target:
        bounded = LimitedOutput(target, report["archive_limit_bytes"])
        with gzip.GzipFile(fileobj=bounded, mode="wb", filename="", mtime=0) as stream:
            while chunk := raw.read(CHUNK):
                deadline.check()
                digest.update(chunk)
                total += len(chunk)
                stream.write(chunk)
                guard.check(metadata["raw_bytes"])
        target.flush()
    if total != metadata["raw_bytes"]:
        raise ValueError("compressed recovery source size changed")
    return {
        "version": "sqlite-gzip-recovery-v1",
        **metadata,
        "raw_sha256": digest.hexdigest(),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": digest_file(archive, deadline),
        "source_integrity": "ok",
        "source_foreign_keys": "ok",
    }
