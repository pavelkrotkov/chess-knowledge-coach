"""Create one bounded, checksummed Zstandard recovery frame."""

from .recovery_gzip_files import digest_file
from .recovery_zstd_native import version
from .recovery_zstd_process import MEMORY_BYTES, transform

LEVEL = 6
WINDOW_LOG = 21
DECODE_WINDOW_BYTES = 8 * 1024 * 1024


def compress(raw, archive, metadata, report, guard, deadline):
    codec_version = version(deadline)
    size = metadata["raw_bytes"]
    arguments = [
        "-q",
        f"-{LEVEL}",
        "--single-thread",
        "--check",
        f"--zstd=wlog={WINDOW_LOG}",
        f"--stream-size={size}",
        "-c",
    ]
    with archive.open("wb", buffering=0) as target:
        result = transform(
            raw,
            target,
            arguments,
            size,
            report["archive_limit_bytes"],
            guard,
            deadline,
            restoring=False,
        )
    return {
        "version": "sqlite-zstd-recovery-v1",
        **metadata,
        "codec": "zstd",
        "codec_version": codec_version,
        "compression_level": LEVEL,
        "window_log": WINDOW_LOG,
        "decode_window_bytes": DECODE_WINDOW_BYTES,
        "codec_memory_bytes": MEMORY_BYTES,
        "threads": 1,
        "checksum": "xxh64",
        "raw_sha256": result["input_sha256"],
        "archive_bytes": result["output_bytes"],
        "archive_sha256": digest_file(archive, deadline),
        "source_integrity": "ok",
        "source_foreign_keys": "ok",
    }
