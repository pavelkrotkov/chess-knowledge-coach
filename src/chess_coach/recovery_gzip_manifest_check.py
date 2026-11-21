"""Validate the versioned compressed-recovery manifest contract."""

import re

FIELDS = {
    "version",
    "page_count",
    "page_size",
    "raw_bytes",
    "user_version",
    "application_id",
    "encoding",
    "raw_sha256",
    "archive_bytes",
    "archive_sha256",
    "source_integrity",
    "source_foreign_keys",
    "restore_integrity",
    "restore_foreign_keys",
    "typed_fidelity",
}
FLAGS = (
    "source_integrity",
    "source_foreign_keys",
    "restore_integrity",
    "restore_foreign_keys",
    "typed_fidelity",
)
PAGE_SIZES = {512, 1024, 2048, 4096, 8192, 16384, 32768, 65536}


def _numbers(value):
    names = (
        "page_count",
        "page_size",
        "raw_bytes",
        "archive_bytes",
        "user_version",
        "application_id",
    )
    if any(type(value[name]) is not int for name in names):
        return False
    if value["page_count"] < 1 or value["page_size"] not in PAGE_SIZES:
        return False
    return (
        value["raw_bytes"] == value["page_count"] * value["page_size"]
        and value["archive_bytes"] > 0
    )


def validate(value):
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError("compressed backup manifest invalid")
    if not _metadata(value) or not _verified(value):
        raise ValueError("compressed backup manifest invalid")


def _metadata(value):
    return (
        value["version"] == "sqlite-gzip-recovery-v1"
        and _numbers(value)
        and isinstance(value["encoding"], str)
        and value["encoding"] in {"UTF-8", "UTF-16le", "UTF-16be"}
    )


def _verified(value):
    return all(value[name] == "ok" for name in FLAGS) and _hashes(value)


def _hashes(value):
    return all(
        isinstance(value[name], str) and re.fullmatch(r"[0-9a-f]{64}", value[name])
        for name in ("raw_sha256", "archive_sha256")
    )
