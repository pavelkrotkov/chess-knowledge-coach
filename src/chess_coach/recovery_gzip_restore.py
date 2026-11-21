"""Restore one gzip archive directly into a separate SQLite file."""

import gzip
import hashlib

from .recovery_gzip_files import digest_file

CHUNK = 64 * 1024


def restore(archive, restored, manifest, guard, deadline):
    if (
        archive.stat().st_size != manifest["archive_bytes"]
        or digest_file(archive, deadline) != manifest["archive_sha256"]
    ):
        raise ValueError("compressed archive verification failed")
    digest = hashlib.sha256()
    total = 0
    with gzip.open(archive, "rb") as stream, restored.open("wb", buffering=0) as target:
        while chunk := stream.read(CHUNK):
            deadline.check()
            total += len(chunk)
            if total > manifest["raw_bytes"]:
                raise ValueError("restored database exceeds snapshot size")
            if target.write(chunk) != len(chunk):
                raise OSError("restored database write incomplete")
            digest.update(chunk)
            guard.check(manifest["raw_bytes"] - total)
    if total != manifest["raw_bytes"] or digest.hexdigest() != manifest["raw_sha256"]:
        raise ValueError("restored database verification failed")
