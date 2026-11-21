"""Validate the distinct versioned Zstandard recovery manifest."""

import re

from .recovery_gzip_manifest_check import FIELDS, _metadata, _verified
from .recovery_zstd_process import MEMORY_BYTES
from .recovery_zstd_stream import DECODE_WINDOW_BYTES, LEVEL, WINDOW_LOG

POLICY = {
    "version": "sqlite-zstd-recovery-v1",
    "codec": "zstd",
    "compression_level": LEVEL,
    "window_log": WINDOW_LOG,
    "decode_window_bytes": DECODE_WINDOW_BYTES,
    "codec_memory_bytes": MEMORY_BYTES,
    "threads": 1,
    "checksum": "xxh64",
}


def validate(value):
    expected = FIELDS | set(POLICY) | {"codec_version"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("compressed backup manifest invalid")
    if any(value[key] != expected for key, expected in POLICY.items()):
        raise ValueError("compressed backup manifest invalid")
    if not _version(value["codec_version"]):
        raise ValueError("compressed backup manifest invalid")
    if not _metadata({**value, "version": "sqlite-gzip-recovery-v1"}) or not _verified(value):
        raise ValueError("compressed backup manifest invalid")


def _version(value):
    return isinstance(value, str) and bool(re.fullmatch(r"\d+\.\d+\.\d+", value))
