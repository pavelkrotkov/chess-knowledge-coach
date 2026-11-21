"""Validate the exact source identity and immutable prefix receipt."""

from .mastery_time import parse_utc
from .opening_queue_files import read
from .opening_recent_source import (
    KIND,
    LICENSE,
    LICENSE_URL,
    MANIFEST_NAME,
    MONTH,
    PREFIX_BYTES,
    SOURCE,
    URL,
)


def _identity(value):
    if parse_utc(value.get("retrieved_at")) is None or not (
        value.get("etag") or value.get("last_modified")
    ):
        raise ValueError("recent source identity unavailable")
    if type(value.get("archive_bytes")) is not int or value["archive_bytes"] <= PREFIX_BYTES:
        raise ValueError("recent source range unavailable")


def receipt(directory):
    path = directory / MANIFEST_NAME
    if path.is_symlink() or path.stat().st_mode & 0o777 != 0o400:
        raise ValueError("recent source receipt unavailable")
    value = read(path)
    expected = {
        "kind": KIND,
        "source_url": URL,
        "month": MONTH,
        "range_start": 0,
        "range_end": PREFIX_BYTES - 1,
        "prefix_bytes": PREFIX_BYTES,
        "source_page": SOURCE,
        "license": LICENSE,
        "license_url": LICENSE_URL,
        "whole_archive_checksum_verified": False,
    }
    if not isinstance(value, dict) or any(value.get(k) != v for k, v in expected.items()):
        raise ValueError("recent source receipt unavailable")
    _identity(value)
    return value
