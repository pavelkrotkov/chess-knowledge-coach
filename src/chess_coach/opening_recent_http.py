"""Validate the fixed anonymous byte-zero response before reading its body."""

import re

from .opening_recent_source import PREFIX_BYTES


def _range(response):
    match = re.fullmatch(r"bytes 0-(\d+)/(\d+)", response.headers.get("content-range", ""))
    if not match or int(match.group(1)) != PREFIX_BYTES - 1 or int(match.group(2)) <= PREFIX_BYTES:
        raise ValueError("public source range differs")
    if response.headers.get("content-length") != str(PREFIX_BYTES):
        raise ValueError("public source range length differs")
    return int(match.group(2))


def validate(response):
    if response.status_code != 206:
        raise ValueError("public source did not provide the requested range")
    if response.headers.get("content-encoding", "identity").lower() != "identity":
        raise ValueError("encoded range response unavailable")
    total = _range(response)
    etag = response.headers.get("etag")
    modified = response.headers.get("last-modified")
    if not etag and not modified:
        raise ValueError("public source response identity unavailable")
    return {"etag": etag, "last_modified": modified, "archive_bytes": total}
