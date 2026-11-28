"""Persist and load the facts proved for an offline recovery pair."""

import json
import stat

from .recovery_gzip_capacity import MANIFEST_ALLOWANCE
from .recovery_gzip_files import publish_bytes

VERSION = "offline-gzip-pair-v1"
VERIFIED = "both_archives_match_sole_leased_source"


def write(path, metadata, first, second):
    value = {
        "version": VERSION,
        "verified": VERIFIED,
        "raw_bytes": metadata["raw_bytes"],
        "raw_sha256": first["raw_sha256"],
        "archives": [
            {"bytes": item["bytes"], "sha256": item["sha256"]} for item in (first, second)
        ],
    }
    publish_bytes(path, (json.dumps(value, sort_keys=True) + "\n").encode())


def _archives(value):
    if not isinstance(value, list):
        raise ValueError("offline pair archive metadata invalid")
    first, second = value
    first["bytes"], first["sha256"]
    second["bytes"], second["sha256"]


def load(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > MANIFEST_ALLOWANCE:
        raise ValueError("offline pair metadata unavailable")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or (value.get("version"), value.get("verified")) != (
        VERSION,
        VERIFIED,
    ):
        raise ValueError("offline pair metadata invalid")
    size = value.get("raw_bytes")
    if type(size) is not int or size <= 0:
        raise ValueError("offline pair source length invalid")
    try:
        value["raw_sha256"]
        _archives(value["archives"])
    except (KeyError, TypeError, ValueError):
        raise ValueError("offline pair metadata fields unavailable") from None
    return value
