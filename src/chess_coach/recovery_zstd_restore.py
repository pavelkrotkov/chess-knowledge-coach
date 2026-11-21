"""Strictly restore one verified Zstandard recovery archive."""

from .recovery_gzip_files import digest_file
from .recovery_zstd_frame import inspect
from .recovery_zstd_process import transform


def restore(archive, restored, manifest, guard, deadline):
    if (
        archive.stat().st_size != manifest["archive_bytes"]
        or digest_file(archive, deadline) != manifest["archive_sha256"]
    ):
        raise ValueError("compressed archive verification failed")
    inspect(archive, deadline)
    with archive.open("rb") as source, restored.open("wb", buffering=0) as target:
        result = transform(
            source,
            target,
            ["-q", "-d", "-M8MB", "-c"],
            manifest["archive_bytes"],
            manifest["raw_bytes"],
            guard,
            deadline,
            restoring=True,
        )
    if (
        result["input_sha256"] != manifest["archive_sha256"]
        or result["output_bytes"] != manifest["raw_bytes"]
        or result["output_sha256"] != manifest["raw_sha256"]
    ):
        raise ValueError("restored database verification failed")
