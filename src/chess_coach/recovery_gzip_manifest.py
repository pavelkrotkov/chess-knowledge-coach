"""Load a retained compressed-backup manifest and check restored metadata."""

import json
import stat
from pathlib import Path

from .recovery_gzip_manifest_check import validate


def load(archive, *, validator=validate):
    path = Path(str(archive) + ".manifest.json")
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > 1024 * 1024:
        raise ValueError("compressed backup manifest unavailable")
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    validator(value)
    if archive.stat().st_size != value["archive_bytes"]:
        raise ValueError("compressed archive verification failed")
    return value


def verify_metadata(connection, value):
    for field in ("page_count", "page_size", "user_version", "application_id", "encoding"):
        if connection.execute("PRAGMA " + field).fetchone()[0] != value[field]:
            raise ValueError("restored database metadata differs from manifest")
